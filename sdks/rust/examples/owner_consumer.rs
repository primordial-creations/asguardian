use gaia_asgard_sdk::{CancellationToken, Client, Options, Request};
use serde_json::json;
#[tokio::main]
async fn main() {
    let args: Vec<String> = std::env::args().collect();
    let command = vec![
        args[1].clone(),
        "-I".into(),
        "-m".into(),
        "Asgard.sdk_protocol".into(),
    ];
    let version = &args[2];
    let c = Client::new(command.clone(), Options::new(version)).unwrap();
    let token = CancellationToken::new();
    let root = std::env::temp_dir().join(format!(
        "scan fixtures {}-{}",
        std::process::id(),
        std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos()
    ));
    std::fs::create_dir(&root).unwrap();
    let root = root.canonicalize().unwrap();
    let target = root.join("source with spaces");
    std::fs::create_dir(&target).unwrap();
    let source = target.join("sample.py");
    std::fs::write(&source, "value = 1\n").unwrap();
    let request = || Request::new(root.to_str().unwrap(), target.to_str().unwrap());
    let hello = c.handshake(&token).await.unwrap();
    assert_eq!(hello["engine_version"], version.as_str());
    assert_eq!(
        hello["capabilities"]["profiles"],
        json!(["quality.file-length"])
    );
    let mut clean_request = request();
    clean_request.correlation_id = "clean".into();
    let clean = c.scan(clean_request, &token).await.unwrap();
    assert_eq!(clean["complete"], true);
    assert_eq!(clean["findings"], json!([]));
    assert_eq!(clean["correlation_id"], "clean");
    std::fs::write(&source, "value = 1\n".repeat(301)).unwrap();
    let finding = c.scan(request(), &token).await.unwrap();
    assert_eq!(finding["complete"], true);
    assert_eq!(finding["findings"].as_array().unwrap().len(), 1);
    assert_eq!(finding["findings"][0]["relative_path"], "sample.py");
    assert_eq!(finding["findings"][0]["lines_over"], 1);
    std::fs::write(target.join("second.py"), "value = 1\n".repeat(302)).unwrap();
    let mut limited = request();
    limited.max_findings = 1;
    let capped = c.scan(limited, &token).await.unwrap();
    assert_eq!(capped["complete"], false);
    assert_eq!(capped["truncated"], true);
    assert_eq!(capped["findings"].as_array().unwrap().len(), 1);
    assert_eq!(capped["summary"]["files_exceeding_threshold"], 2);
    for invalid in [root.join("missing"), root.parent().unwrap().to_owned()] {
        let error = c
            .scan(
                Request::new(root.to_str().unwrap(), invalid.to_str().unwrap()),
                &token,
            )
            .await
            .unwrap_err();
        assert_eq!(error.code, "engine_error");
        assert_eq!(
            error.response.unwrap()["errors"][0]["code"],
            "invalid_request"
        );
    }
    let linked = root.join("linked");
    std::fs::create_dir(&linked).unwrap();
    std::os::unix::fs::symlink(&source, linked.join("escape.py")).unwrap();
    let partial = c
        .scan(
            Request::new(linked.to_str().unwrap(), linked.to_str().unwrap()),
            &token,
        )
        .await
        .unwrap();
    assert_eq!(partial["complete"], false);
    assert_eq!(partial["findings"], json!([]));
    assert_eq!(partial["errors"][0]["code"], "scan_io_failure");
    let wrong = Client::new(command, Options::new(format!("{version}-wrong"))).unwrap();
    let error = wrong.handshake(&token).await.unwrap_err();
    assert_eq!(error.code, "engine_version_mismatch");
    wrong.close().await;
    c.close().await;
    std::fs::remove_dir_all(root).unwrap();
    println!(
        "{}",
        json!({"clean":clean["state"],"finding":finding["findings"][0]["lines_over"],"truncated":capped["state"],"invalid_target":"invalid_request","symlink":partial["state"],"mismatch":error.code})
    );
}
