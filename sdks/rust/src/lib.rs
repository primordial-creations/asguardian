//! Owner process client. Host authorization and a separately pinned engine are required.
#![cfg(unix)]
use serde_json::{json, Value};
use std::{
    path::Path,
    process::Stdio,
    sync::{Arc, Mutex},
    time::Duration,
};
use tokio::{
    io::{AsyncRead, AsyncReadExt, AsyncWriteExt},
    process::Command,
    sync::watch,
    time::Instant,
};
pub use tokio_util::sync::CancellationToken;

#[derive(Debug)]
pub struct Error {
    pub code: &'static str,
    pub response: Option<Value>,
}
impl std::fmt::Display for Error {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(self.code)
    }
}
impl std::error::Error for Error {}
fn fail(code: &'static str) -> Error {
    Error {
        code,
        response: None,
    }
}
#[derive(Clone)]
pub struct Options {
    pub engine_version: String,
    pub timeout: Duration,
    pub max_output_bytes: usize,
}
impl Options {
    pub fn new(engine_version: impl Into<String>) -> Self {
        Self {
            engine_version: engine_version.into(),
            timeout: Duration::from_secs(120),
            max_output_bytes: 20 * 1024 * 1024,
        }
    }
}
pub struct Request {
    pub logical_root: Option<String>,
    pub authorized_root: String,
    pub target: String,
    pub profile: String,
    pub max_findings: usize,
    pub correlation_id: String,
}
impl Request {
    pub fn new(root: impl Into<String>, target: impl Into<String>) -> Self {
        Self {
            logical_root: None,
            authorized_root: root.into(),
            target: target.into(),
            profile: "quality.file-length".into(),
            max_findings: 1000,
            correlation_id: correlation(),
        }
    }
}
fn correlation() -> String {
    static NEXT: std::sync::atomic::AtomicU64 = std::sync::atomic::AtomicU64::new(0);
    format!(
        "{}-{:?}-{}",
        std::process::id(),
        std::time::SystemTime::now(),
        NEXT.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
    )
}
struct Inner {
    command: Vec<String>,
    options: Options,
    gate: Mutex<bool>,
    count: watch::Sender<usize>,
    closed: CancellationToken,
}
pub struct Client {
    inner: Arc<Inner>,
}
impl Drop for Client {
    fn drop(&mut self) {
        self.inner.closed.cancel();
    }
}
struct Count(Arc<Inner>);
impl Drop for Count {
    fn drop(&mut self) {
        self.0.count.send_modify(|n| *n -= 1);
    }
}
struct Group(i32);
impl Group {
    fn kill(&mut self) -> Result<(), Error> {
        if self.0 == 0 {
            return Ok(());
        }
        // SAFETY: this PID was returned by our spawned child, made leader of its own group.
        let result = unsafe { libc::kill(-self.0, libc::SIGKILL) };
        if result == 0 || std::io::Error::last_os_error().raw_os_error() == Some(libc::ESRCH) {
            self.0 = 0;
            Ok(())
        } else {
            Err(fail("process_cleanup_failed"))
        }
    }
}
impl Drop for Group {
    fn drop(&mut self) {
        let _ = self.kill();
    }
}
impl Client {
    pub fn new(command: Vec<String>, options: Options) -> Result<Self, Error> {
        if command.is_empty()
            || !Path::new(&command[0]).is_absolute()
            || command.iter().any(|s| s.is_empty() || s.contains('\0'))
            || options.engine_version.is_empty()
            || options.timeout.is_zero()
            || options.max_output_bytes < 1024
        {
            return Err(fail("invalid_configuration"));
        }
        let (count, _) = watch::channel(0);
        Ok(Self {
            inner: Arc::new(Inner {
                command,
                options,
                gate: Mutex::new(false),
                count,
                closed: CancellationToken::new(),
            }),
        })
    }
    pub async fn close(&self) {
        {
            let mut gate = self.inner.gate.lock().expect("client lock poisoned");
            *gate = true;
            self.inner.closed.cancel();
        }
        let mut count = self.inner.count.subscribe();
        let _ = count.wait_for(|n| *n == 0).await;
    }
    pub async fn handshake(&self, cancel: &CancellationToken) -> Result<Value, Error> {
        self.invoke(
            json!({"protocol_version":1,"operation":"handshake","correlation_id":correlation()}),
            Instant::now() + self.inner.options.timeout,
            cancel,
        )
        .await
    }
    pub async fn scan(&self, request: Request, cancel: &CancellationToken) -> Result<Value, Error> {
        let deadline = Instant::now() + self.inner.options.timeout;
        if request.correlation_id.is_empty() || request.correlation_id.chars().count() > 256 {
            return Err(fail("invalid_request"));
        }
        let hello=self.invoke(json!({"protocol_version":1,"operation":"handshake","correlation_id":request.correlation_id}),deadline,cancel).await?;
        if !hello["capabilities"]["profiles"]
            .as_array()
            .unwrap()
            .contains(&json!(request.profile))
        {
            return Err(fail("unsupported_operation"));
        }
        let mut payload = json!({"protocol_version":1,"operation":"scan","correlation_id":request.correlation_id,"profile":request.profile,"authorized_root":request.authorized_root,"target":request.target,"max_findings":request.max_findings});
        if let Some(label) = request.logical_root {
            if !hello["capabilities"]["logical_paths"]
                .as_array()
                .is_some_and(|profiles| profiles.contains(&json!(request.profile)))
            {
                return Err(fail("unsupported_operation"));
            }
            payload["logical_root"] = json!(label);
        }
        self.invoke(payload, deadline, cancel).await
    }
    async fn invoke(
        &self,
        request: Value,
        deadline: Instant,
        cancel: &CancellationToken,
    ) -> Result<Value, Error> {
        {
            let gate = self.inner.gate.lock().expect("client lock poisoned");
            if *gate || self.inner.closed.is_cancelled() {
                return Err(fail("closed"));
            }
            if cancel.is_cancelled() {
                return Err(fail("cancelled"));
            }
            self.inner.count.send_modify(|n| *n += 1);
        }
        let count = Count(self.inner.clone());
        let inner = self.inner.clone();
        let operation = cancel.child_token();
        let guard = operation.clone().drop_guard();
        let task = tokio::spawn(async move {
            let _count = count;
            run(inner, request, deadline, operation).await
        });
        let result = task.await.map_err(|_| fail("process_task_failed"))?;
        drop(guard);
        result
    }
}
async fn read_bounded(
    mut input: impl AsyncRead + Unpin,
    limit: usize,
    retain: bool,
) -> Result<Vec<u8>, Error> {
    let mut output = Vec::new();
    let mut total = 0usize;
    let mut buffer = [0u8; 8192];
    loop {
        let n = input
            .read(&mut buffer)
            .await
            .map_err(|_| fail("transport_error"))?;
        if n == 0 {
            return Ok(output);
        };
        if n > limit - total {
            return Err(fail("output_limit"));
        }
        total += n;
        if retain {
            output.extend_from_slice(&buffer[..n]);
        }
    }
}
async fn run(
    inner: Arc<Inner>,
    request: Value,
    deadline: Instant,
    cancel: CancellationToken,
) -> Result<Value, Error> {
    if inner.closed.is_cancelled() {
        return Err(fail("closed"));
    }
    if cancel.is_cancelled() {
        return Err(fail("cancelled"));
    }
    if Instant::now() >= deadline {
        return Err(fail("timeout"));
    }
    let raw = serde_json::to_vec(&request).map_err(|_| fail("invalid_request"))?;
    if raw.len() > 65536 {
        return Err(fail("request_too_large"));
    }
    let mut command = Command::new(&inner.command[0]);
    command
        .args(&inner.command[1..])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .kill_on_drop(true);
    command.process_group(0);
    let mut child = command.spawn().map_err(|_| fail("engine_unavailable"))?;
    let mut group = Group(child.id().unwrap() as i32);
    let mut input = child.stdin.take().unwrap();
    let stdout = child.stdout.take().unwrap();
    let stderr = child.stderr.take().unwrap();
    let result = {
        let io = async {
            tokio::try_join!(
                async {
                    input
                        .write_all(&raw)
                        .await
                        .map_err(|_| fail("transport_error"))?;
                    drop(input);
                    Ok::<(), Error>(())
                },
                read_bounded(stdout, inner.options.max_output_bytes, true),
                read_bounded(stderr, inner.options.max_output_bytes, false),
                async { child.wait().await.map_err(|_| fail("transport_error")) }
            )
        };
        tokio::select! {biased;
         _=inner.closed.cancelled()=>Err(fail("closed")),
         _=cancel.cancelled()=>Err(fail("cancelled")),
         _=tokio::time::sleep_until(deadline)=>Err(fail("timeout")),
         result=io=>result,
        }
    };
    let cleanup = group.kill();
    let _ = child.wait().await;
    let (_, output, _, status) = result?;
    cleanup?;
    decode(
        &output,
        status.code(),
        &request,
        &inner.options.engine_version,
    )
}
fn decode(raw: &[u8], code: Option<i32>, request: &Value, version: &str) -> Result<Value, Error> {
    let r: Value = serde_json::from_slice(raw).map_err(|_| fail("malformed_response"))?;
    if !r.is_object() {
        return Err(fail("malformed_response"));
    }
    if r["protocol_version"] != json!(1) {
        return Err(fail("version_mismatch"));
    }
    if r["engine_version"] != version {
        return Err(fail("engine_version_mismatch"));
    }
    let complete = r["complete"]
        .as_bool()
        .ok_or_else(|| fail("malformed_response"))?;
    let truncated = r["truncated"]
        .as_bool()
        .ok_or_else(|| fail("malformed_response"))?;
    let findings = r["findings"]
        .as_array()
        .ok_or_else(|| fail("malformed_response"))?;
    let errors = r["errors"]
        .as_array()
        .ok_or_else(|| fail("malformed_response"))?;
    if r["correlation_id"] != request["correlation_id"]
        || r["scan_id"].as_str().is_none_or(str::is_empty)
        || !findings.iter().chain(errors.iter()).all(Value::is_object)
    {
        return Err(fail("malformed_response"));
    }
    if r["state"] == "error" && code == Some(2) && !complete && !errors.is_empty() {
        return Err(Error {
            code: "engine_error",
            response: Some(r),
        });
    }
    let valid = if request["operation"] == "handshake" {
        r["state"] == "ready"
            && code == Some(0)
            && complete
            && !truncated
            && findings.is_empty()
            && errors.is_empty()
            && r["capabilities"]["profiles"].is_array()
            && r["capabilities"]["transport"] == "single-request-stdio"
    } else {
        (r["state"] == "complete"
            && complete
            && !truncated
            && errors.is_empty()
            && code == Some(if findings.is_empty() { 0 } else { 1 }))
            || (r["state"] == "incomplete"
                && !complete
                && code == Some(1)
                && (truncated || !errors.is_empty()))
    };
    if !valid {
        return Err(fail("malformed_response"));
    }
    Ok(r)
}
