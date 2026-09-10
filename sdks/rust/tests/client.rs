use gaia_asgard_sdk::{CancellationToken, Client, Options, Request};
use std::{sync::Arc, time::Duration};
const FIXTURE: &str = r#"
import json,sys,time,subprocess
r=json.load(sys.stdin);mode=sys.argv[1]
if mode.startswith('child='):
 child=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)'])
 with open(mode[6:],'w') as f:f.write(str(child.pid))
 time.sleep(60)
if mode=='sleep':time.sleep(60)
if mode in ('stdout','stderr'):
 getattr(sys,mode).write('x'*100000);getattr(sys,mode).flush();time.sleep(60)
if mode=='malformed':print('null');sys.exit(0)
v=dict(protocol_version=1,engine_version='fixture',scan_id='id',correlation_id=r['correlation_id'],state='ready',complete=True,truncated=False,findings=[],errors=[],capabilities=dict(profiles=['quality.file-length'],transport='single-request-stdio'))
code=0
if r['operation']=='scan':
 v['state']='complete'
 if mode=='finding':v['findings']=[dict(relative_path='sample.py')];code=1
 if mode=='incomplete':v.update(state='incomplete',complete=False,truncated=True);code=1
 if mode=='lying':v['errors']=[dict(code='missing_tool')]
 if mode=='error':v.update(state='error',complete=False,errors=[dict(code='invalid_request')]);code=2
if mode=='version':v['engine_version']='other'
print(json.dumps(v));sys.exit(code)
"#;
fn client(mode: &str, timeout: u64) -> Client {
    let mut options = Options::new("fixture");
    options.timeout = Duration::from_millis(timeout);
    options.max_output_bytes = 1024;
    Client::new(
        vec![
            std::env::var("ASGARD_TEST_PYTHON").unwrap_or("/usr/bin/python3".into()),
            "-c".into(),
            FIXTURE.into(),
            mode.into(),
        ],
        options,
    )
    .unwrap()
}
fn request() -> Request {
    Request::new("/fixture", "/fixture/source")
}
#[tokio::test]
async fn truth() {
    for mode in ["clean", "finding", "incomplete"] {
        let c = client(mode, 3000);
        let r = c.scan(request(), &CancellationToken::new()).await.unwrap();
        assert_eq!(r["complete"], mode != "incomplete");
        assert_eq!(
            r["findings"].as_array().unwrap().len(),
            usize::from(mode == "finding")
        );
        c.close().await;
    }
}
#[tokio::test]
async fn failures() {
    for (mode, code) in [
        ("malformed", "malformed_response"),
        ("lying", "malformed_response"),
        ("version", "engine_version_mismatch"),
        ("error", "engine_error"),
    ] {
        let c = client(mode, 3000);
        let error = c
            .scan(request(), &CancellationToken::new())
            .await
            .unwrap_err();
        assert_eq!(error.code, code);
        if mode == "error" {
            assert_eq!(
                error.response.unwrap()["errors"][0]["code"],
                "invalid_request"
            );
        }
        c.close().await;
    }
}
#[tokio::test]
async fn bounds() {
    for mode in ["sleep", "stdout", "stderr"] {
        let c = client(mode, 300);
        assert_eq!(
            c.handshake(&CancellationToken::new())
                .await
                .unwrap_err()
                .code,
            if mode == "sleep" {
                "timeout"
            } else {
                "output_limit"
            }
        );
        c.close().await;
    }
}
#[tokio::test]
async fn cancellation_and_close() {
    for close in [false, true] {
        let c = Arc::new(client("sleep", 3000));
        let token = CancellationToken::new();
        let task_client = c.clone();
        let task_token = token.clone();
        let task = tokio::spawn(async move { task_client.handshake(&task_token).await });
        tokio::time::sleep(Duration::from_millis(80)).await;
        if close {
            c.close().await;
        } else {
            token.cancel();
        }
        assert_eq!(
            task.await.unwrap().unwrap_err().code,
            if close { "closed" } else { "cancelled" }
        );
        c.close().await;
        assert_eq!(
            c.handshake(&CancellationToken::new())
                .await
                .unwrap_err()
                .code,
            "closed"
        );
    }
}
#[tokio::test]
async fn independent_and_unsupported() {
    let first = client("clean", 3000);
    let second = client("clean", 3000);
    first.close().await;
    assert!(second
        .scan(request(), &CancellationToken::new())
        .await
        .unwrap()["complete"]
        .as_bool()
        .unwrap());
    let mut r = request();
    r.profile = "other".into();
    assert_eq!(
        second
            .scan(r, &CancellationToken::new())
            .await
            .unwrap_err()
            .code,
        "unsupported_operation"
    );
    second.close().await;
    let missing = Client::new(vec!["/nonexistent/asgard".into()], Options::new("1")).unwrap();
    assert_eq!(
        missing
            .handshake(&CancellationToken::new())
            .await
            .unwrap_err()
            .code,
        "engine_unavailable"
    );
    missing.close().await;
}
#[tokio::test]
async fn dropped_future_cleans_child_group() {
    let marker = std::env::temp_dir().join(format!(
        "asgard-child-{}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    let c = Arc::new(client(&format!("child={}", marker.display()), 3000));
    let operation = c.clone();
    let task = tokio::spawn(async move { operation.handshake(&CancellationToken::new()).await });
    let deadline = tokio::time::Instant::now() + Duration::from_secs(2);
    while !marker.exists() {
        assert!(tokio::time::Instant::now() < deadline);
        tokio::time::sleep(Duration::from_millis(10)).await;
    }
    task.abort();
    let _ = task.await;
    tokio::time::timeout(Duration::from_secs(2), c.close())
        .await
        .unwrap();
    let pid = std::fs::read_to_string(&marker).unwrap();
    // SIGKILL delivery to the group is asynchronous. close reaps the direct
    // child; its orphaned grandchild must also stop within a bounded interval.
    let deadline = tokio::time::Instant::now() + Duration::from_secs(2);
    loop {
        match std::fs::read_to_string(format!("/proc/{pid}/stat")) {
            Ok(stat) if stat.split_whitespace().nth(2) != Some("Z") => {
                assert!(
                    tokio::time::Instant::now() < deadline,
                    "grandchild survived group cleanup"
                );
                tokio::time::sleep(Duration::from_millis(10)).await;
            }
            Ok(_) => break,
            Err(error) if error.kind() == std::io::ErrorKind::NotFound => break,
            Err(error) => panic!("could not verify grandchild cleanup: {error}"),
        }
    }
    std::fs::remove_file(marker).unwrap();
}

#[tokio::test]
async fn closed_takes_precedence_over_precancelled() {
    let c = client("sleep", 3000);
    let cancel = CancellationToken::new();
    cancel.cancel();
    c.close().await;
    assert_eq!(c.handshake(&cancel).await.unwrap_err().code, "closed");
}
