use serde::Serialize;
use std::{
    env,
    fs::{self, File, OpenOptions},
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::{
        atomic::{AtomicBool, Ordering},
        Arc, Condvar, Mutex,
    },
    thread,
    time::{Duration, Instant, SystemTime, UNIX_EPOCH},
};
use tauri::{AppHandle, Emitter, Manager, RunEvent, State};
use uuid::Uuid;

const STATUS_EVENT: &str = "backend-status";
const STDERR_LOG_NAME: &str = "backend-stderr.log";
const STDERR_LOG_MAX_BYTES: u64 = 2_000_000;
const RESTART_LIMIT: usize = 3;
const RESTART_WINDOW: Duration = Duration::from_secs(300);
const SUPERVISE_INTERVAL: Duration = Duration::from_secs(2);
const SHUTDOWN_GRACE: Duration = Duration::from_secs(5);
const CONNECTION_WAIT: Duration = Duration::from_secs(90);

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendConnection {
    base_url: String,
    session_token: String,
}

/// What the frontend is told about the local service. Serialised as `{"state": "...", ...}`.
#[derive(Clone, Debug, PartialEq, Serialize)]
#[serde(tag = "state", rename_all = "lowercase")]
enum BackendStatus {
    Starting,
    Ready,
    Restarting { message: String },
    Failed { message: String },
}

#[derive(Clone)]
enum Launch {
    Development { backend_directory: PathBuf },
    Packaged { executable: PathBuf },
}

/// Restarts allowed within a rolling window, so a backend that crashes on every start does not
/// restart forever.
struct RestartBudget {
    limit: usize,
    window: Duration,
    recent: Vec<Instant>,
}

impl RestartBudget {
    fn new(limit: usize, window: Duration) -> Self {
        Self {
            limit,
            window,
            recent: Vec::new(),
        }
    }

    fn try_take(&mut self, now: Instant) -> bool {
        self.recent
            .retain(|started| now.saturating_duration_since(*started) < self.window);
        if self.recent.len() >= self.limit {
            return false;
        }
        self.recent.push(now);
        true
    }
}

struct Supervisor {
    launch: Option<Launch>,
    port: u16,
    token: String,
    connection: BackendConnection,
    status: Mutex<BackendStatus>,
    status_changed: Condvar,
    child: Mutex<Option<Child>>,
    shutting_down: AtomicBool,
    restarts: Mutex<RestartBudget>,
    log_directory: PathBuf,
}

impl Supervisor {
    fn set_status(&self, handle: Option<&AppHandle>, status: BackendStatus) {
        if let Ok(mut current) = self.status.lock() {
            *current = status.clone();
        }
        self.status_changed.notify_all();
        if let Some(handle) = handle {
            let _ = handle.emit(STATUS_EVENT, &status);
        }
    }

    fn wait_until_settled(&self, timeout: Duration) -> Result<BackendConnection, String> {
        let deadline = Instant::now() + timeout;
        let mut status = self
            .status
            .lock()
            .map_err(|_| "The local service state is unavailable.".to_string())?;
        loop {
            match &*status {
                BackendStatus::Ready => return Ok(self.connection.clone()),
                BackendStatus::Failed { message } => return Err(message.clone()),
                BackendStatus::Starting | BackendStatus::Restarting { .. } => {}
            }
            let remaining = deadline.saturating_duration_since(Instant::now());
            if remaining.is_zero() {
                return Err("The local service is still starting. Try again shortly.".to_string());
            }
            status = self
                .status_changed
                .wait_timeout(status, remaining)
                .map_err(|_| "The local service state is unavailable.".to_string())?
                .0;
        }
    }

    fn failure_message(&self, detail: &str) -> String {
        format!(
            "The local service could not start: {detail}. Details are in {}.",
            self.log_directory.join(STDERR_LOG_NAME).display()
        )
    }

    /// Starts the backend and waits until it accepts connections.
    fn start(&self) -> Result<(), String> {
        let launch = self
            .launch
            .clone()
            .ok_or_else(|| "the backend program was not found".to_string())?;
        let stderr = open_stderr_log(&self.log_directory, self.port);
        let mut child = match &launch {
            Launch::Development { backend_directory } => {
                spawn_backend(backend_directory, self.port, &self.token, None, stderr)?
            }
            Launch::Packaged { executable } => {
                spawn_packaged_backend(executable, self.port, &self.token, None, stderr)?
            }
        };
        if let Err(error) = wait_for_backend(&mut child, self.port) {
            let _ = child.kill();
            let _ = child.wait();
            return Err(error);
        }
        if let Ok(mut guard) = self.child.lock() {
            *guard = Some(child);
        }
        Ok(())
    }

    /// Watches the running backend and restarts it, within budget, if it exits unexpectedly.
    fn supervise(&self, handle: &AppHandle) {
        loop {
            thread::sleep(SUPERVISE_INTERVAL);
            if self.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            let exited = match self.child.lock() {
                Ok(mut guard) => match guard.as_mut() {
                    Some(child) => child.try_wait().ok().flatten(),
                    None => return,
                },
                Err(_) => return,
            };
            let Some(status) = exited else { continue };
            if self.shutting_down.load(Ordering::SeqCst) {
                return;
            }
            append_stderr_note(
                &self.log_directory,
                &format!("backend exited unexpectedly with {status}"),
            );
            let allowed = self
                .restarts
                .lock()
                .map(|mut budget| budget.try_take(Instant::now()))
                .unwrap_or(false);
            if !allowed {
                let message = self.failure_message("it stopped repeatedly and was not restarted");
                self.set_status(Some(handle), BackendStatus::Failed { message });
                return;
            }
            self.set_status(
                Some(handle),
                BackendStatus::Restarting {
                    message: "The local service stopped unexpectedly and is restarting."
                        .to_string(),
                },
            );
            match self.start() {
                Ok(()) => {
                    append_stderr_note(&self.log_directory, "backend restarted");
                    self.set_status(Some(handle), BackendStatus::Ready);
                }
                Err(error) => {
                    let message = self.failure_message(&error);
                    self.set_status(Some(handle), BackendStatus::Failed { message });
                    return;
                }
            }
        }
    }

    /// Asks the backend to shut down cleanly, and only kills it if it does not exit in time.
    fn stop(&self) {
        self.shutting_down.store(true, Ordering::SeqCst);
        let child = self.child.lock().ok().and_then(|mut guard| guard.take());
        let Some(mut child) = child else { return };
        let _ = request_shutdown(self.port, &self.token);
        let deadline = Instant::now() + SHUTDOWN_GRACE;
        while Instant::now() < deadline {
            if let Ok(Some(_)) = child.try_wait() {
                return;
            }
            thread::sleep(Duration::from_millis(100));
        }
        append_stderr_note(
            &self.log_directory,
            "backend did not exit within the grace period; stopping it",
        );
        let _ = child.kill();
        let _ = child.wait();
    }
}

#[tauri::command(async)]
fn backend_connection(state: State<'_, Arc<Supervisor>>) -> Result<BackendConnection, String> {
    state.wait_until_settled(CONNECTION_WAIT)
}

fn log_directory() -> PathBuf {
    if let Some(configured) = env::var_os("ENS_LOG_DIRECTORY") {
        return PathBuf::from(configured);
    }
    let base = env::var_os("LOCALAPPDATA")
        .map(PathBuf::from)
        .unwrap_or_else(env::temp_dir);
    base.join("EtchNShine").join("LeadGeneration").join("logs")
}

fn unix_seconds() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_secs())
        .unwrap_or_default()
}

/// The backend's stdout and stderr, appended to a log file that is rotated once it is large.
/// Falls back to discarding output if the file cannot be opened, rather than failing startup.
fn open_stderr_log(directory: &Path, port: u16) -> Option<File> {
    fs::create_dir_all(directory).ok()?;
    let path = directory.join(STDERR_LOG_NAME);
    if fs::metadata(&path).map(|meta| meta.len()).unwrap_or(0) > STDERR_LOG_MAX_BYTES {
        let _ = fs::rename(&path, directory.join(format!("{STDERR_LOG_NAME}.1")));
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .ok()?;
    let _ = writeln!(
        file,
        "--- backend start at unix time {} on loopback port {port} ---",
        unix_seconds()
    );
    Some(file)
}

fn append_stderr_note(directory: &Path, note: &str) {
    if let Ok(mut file) = OpenOptions::new()
        .create(true)
        .append(true)
        .open(directory.join(STDERR_LOG_NAME))
    {
        let _ = writeln!(
            file,
            "--- desktop host at unix time {}: {note} ---",
            unix_seconds()
        );
    }
}

fn output_streams(stderr: Option<File>) -> (Stdio, Stdio) {
    match stderr {
        Some(file) => {
            let stdout = file
                .try_clone()
                .map(Stdio::from)
                .unwrap_or_else(|_| Stdio::null());
            (stdout, Stdio::from(file))
        }
        None => (Stdio::null(), Stdio::null()),
    }
}

fn find_backend_directory() -> Result<PathBuf, String> {
    if let Some(configured) = env::var_os("ENS_BACKEND_DIR") {
        let path = PathBuf::from(configured);
        if path.join("app").join("cli.py").is_file() {
            return path.canonicalize().map_err(|error| error.to_string());
        }
    }
    let current = env::current_dir().map_err(|error| error.to_string())?;
    let candidates = [
        current.join("..").join("backend"),
        current.join("apps").join("backend"),
        current.join("..").join("..").join("backend"),
    ];
    candidates
        .into_iter()
        .find(|path| path.join("app").join("cli.py").is_file())
        .and_then(|path| path.canonicalize().ok())
        .ok_or_else(|| {
            "Backend source was not found. Set ENS_BACKEND_DIR for development; release builds require a bundled sidecar."
                .to_string()
        })
}

fn select_loopback_port() -> Result<u16, String> {
    let listener = TcpListener::bind(("127.0.0.1", 0)).map_err(|error| error.to_string())?;
    listener
        .local_addr()
        .map(|address| address.port())
        .map_err(|error| error.to_string())
}

fn find_python(backend_directory: &Path) -> PathBuf {
    if let Some(configured) = env::var_os("ENS_PYTHON_EXECUTABLE") {
        return PathBuf::from(configured);
    }
    let executable = if cfg!(target_os = "windows") {
        PathBuf::from("Scripts").join("python.exe")
    } else {
        PathBuf::from("bin").join("python")
    };
    let candidates = [
        backend_directory.join(".venv").join(&executable),
        backend_directory
            .parent()
            .and_then(Path::parent)
            .map(|root| root.join(".venv").join(&executable))
            .unwrap_or_default(),
    ];
    candidates
        .into_iter()
        .find(|path| path.is_file())
        .unwrap_or_else(|| PathBuf::from("python"))
}

fn spawn_backend(
    backend_directory: &Path,
    port: u16,
    token: &str,
    database_path: Option<&Path>,
    stderr: Option<File>,
) -> Result<Child, String> {
    let python = find_python(backend_directory);
    let (stdout, stderr) = output_streams(stderr);
    let mut command = Command::new(python);
    command
        .args(["-m", "app.cli", "serve"])
        .current_dir(backend_directory)
        .env("ENS_HOST", "127.0.0.1")
        .env("ENS_PORT", port.to_string())
        .env("ENS_SESSION_TOKEN", token)
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);
    if let Some(path) = database_path {
        command.env("ENS_DATABASE_PATH", path);
    }

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }

    command.spawn().map_err(|error| error.to_string())
}

fn packaged_backend_path(application: &tauri::App) -> Option<PathBuf> {
    let executable_name = if cfg!(target_os = "windows") {
        "ens-backend.exe"
    } else {
        "ens-backend"
    };
    let beside_executable = env::current_exe()
        .ok()
        .and_then(|path| path.parent().map(Path::to_path_buf))
        .map(|directory| directory.join("ens-backend").join(executable_name));
    if let Some(path) = beside_executable.filter(|path| path.is_file()) {
        return Some(path);
    }
    application
        .path()
        .resource_dir()
        .ok()
        .map(|directory| directory.join("ens-backend").join(executable_name))
        .filter(|path| path.is_file())
}

fn spawn_packaged_backend(
    executable: &Path,
    port: u16,
    token: &str,
    runtime_directory: Option<&Path>,
    stderr: Option<File>,
) -> Result<Child, String> {
    let (stdout, stderr) = output_streams(stderr);
    let mut command = Command::new(executable);
    command
        .arg("serve")
        .env("ENS_HOST", "127.0.0.1")
        .env("ENS_PORT", port.to_string())
        .env("ENS_SESSION_TOKEN", token)
        .stdin(Stdio::null())
        .stdout(stdout)
        .stderr(stderr);
    if let Some(directory) = runtime_directory {
        command
            .env("ENS_DATABASE_PATH", directory.join("smoke.db"))
            .env("ENS_LOG_DIRECTORY", directory.join("logs"));
    }

    #[cfg(target_os = "windows")]
    {
        use std::os::windows::process::CommandExt;
        command.creation_flags(0x08000000);
    }

    command.spawn().map_err(|error| error.to_string())
}

fn http_request(port: u16, method: &str, path: &str, token: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).map_err(|error| error.to_string())?;
    stream
        .set_read_timeout(Some(Duration::from_secs(5)))
        .map_err(|error| error.to_string())?;
    let request = format!(
        "{method} {path} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Session-Token: {token}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
    );
    stream
        .write_all(request.as_bytes())
        .map_err(|error| error.to_string())?;
    let mut response = String::new();
    stream
        .read_to_string(&mut response)
        .map_err(|error| error.to_string())?;
    Ok(response)
}

fn request_authenticated_health(port: u16, token: &str) -> Result<String, String> {
    http_request(port, "GET", "/api/v1/health", token)
}

fn request_shutdown(port: u16, token: &str) -> Result<String, String> {
    http_request(port, "POST", "/api/v1/system/shutdown", token)
}

fn run_packaged_smoke_test() -> Result<(), String> {
    let executable_name = if cfg!(target_os = "windows") {
        "ens-backend.exe"
    } else {
        "ens-backend"
    };
    let executable = env::current_exe()
        .map_err(|error| error.to_string())?
        .parent()
        .map(|directory| directory.join("ens-backend").join(executable_name))
        .filter(|path| path.is_file())
        .ok_or_else(|| {
            "Packaged backend resource was not found beside the desktop host".to_string()
        })?;
    let runtime_directory = env::temp_dir().join(format!("ens-release-smoke-{}", Uuid::new_v4()));
    std::fs::create_dir_all(&runtime_directory).map_err(|error| error.to_string())?;
    let port = select_loopback_port()?;
    let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
    let mut child = spawn_packaged_backend(
        &executable,
        port,
        &token,
        Some(runtime_directory.as_path()),
        None,
    )?;
    let outcome = (|| {
        wait_for_backend(&mut child, port)?;
        let response = request_authenticated_health(port, &token)?;
        if !response.starts_with("HTTP/1.1 200") {
            return Err(format!("Packaged backend health failed: {response}"));
        }
        Ok(())
    })();
    let _ = child.kill();
    let _ = child.wait();
    thread::sleep(Duration::from_millis(200));
    let _ = std::fs::remove_dir_all(runtime_directory);
    outcome
}

// A cold start from a synced folder, with pending migrations, can take well over ten seconds.
fn wait_for_backend(child: &mut Child, port: u16) -> Result<(), String> {
    for _ in 0..300 {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return Ok(());
        }
        if let Some(status) = child.try_wait().map_err(|error| error.to_string())? {
            return Err(format!("the backend exited during startup with {status}"));
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("the backend did not become ready within 30 seconds".to_string())
}

fn select_launch(application: &tauri::App) -> Option<Launch> {
    if cfg!(debug_assertions) {
        find_backend_directory()
            .ok()
            .map(|backend_directory| Launch::Development { backend_directory })
    } else {
        packaged_backend_path(application).map(|executable| Launch::Packaged { executable })
    }
}

pub fn run() {
    if env::args_os().any(|argument| argument == "--smoke-test") {
        if let Err(error) = run_packaged_smoke_test() {
            eprintln!("{error}");
            std::process::exit(1);
        }
        println!("Packaged desktop/backend smoke test passed");
        return;
    }
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .setup(|application| {
            let port = select_loopback_port()?;
            let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
            let supervisor = Arc::new(Supervisor {
                launch: select_launch(application),
                port,
                connection: BackendConnection {
                    base_url: format!("http://127.0.0.1:{port}/api/v1"),
                    session_token: token.clone(),
                },
                token,
                status: Mutex::new(BackendStatus::Starting),
                status_changed: Condvar::new(),
                child: Mutex::new(None),
                shutting_down: AtomicBool::new(false),
                restarts: Mutex::new(RestartBudget::new(RESTART_LIMIT, RESTART_WINDOW)),
                log_directory: log_directory(),
            });
            application.manage(Arc::clone(&supervisor));
            // The window opens at once; the backend starts in the background and the frontend
            // waits for it through `backend_connection`, which reports a failure instead of
            // the app silently closing.
            let handle = application.handle().clone();
            thread::spawn(move || match supervisor.start() {
                Ok(()) => {
                    supervisor.set_status(Some(&handle), BackendStatus::Ready);
                    supervisor.supervise(&handle);
                }
                Err(error) => {
                    let message = supervisor.failure_message(&error);
                    append_stderr_note(&supervisor.log_directory, &message);
                    supervisor.set_status(Some(&handle), BackendStatus::Failed { message });
                }
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_connection])
        .build(tauri::generate_context!())
        .expect("failed to build Etch 'N' Shine desktop application");

    app.run(|handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            handle.state::<Arc<Supervisor>>().stop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn restart_budget_allows_a_limited_number_within_the_window() {
        let mut budget = RestartBudget::new(3, Duration::from_secs(300));
        let start = Instant::now();
        assert!(budget.try_take(start));
        assert!(budget.try_take(start + Duration::from_secs(10)));
        assert!(budget.try_take(start + Duration::from_secs(20)));
        assert!(!budget.try_take(start + Duration::from_secs(30)));
        // Once the oldest restart leaves the window, one more is allowed.
        assert!(budget.try_take(start + Duration::from_secs(301)));
    }

    #[test]
    fn backend_status_serialises_with_a_state_tag() {
        let failed = serde_json::to_string(&BackendStatus::Failed {
            message: "boom".to_string(),
        })
        .expect("serialise");
        assert_eq!(failed, r#"{"state":"failed","message":"boom"}"#);
        let ready = serde_json::to_string(&BackendStatus::Ready).expect("serialise");
        assert_eq!(ready, r#"{"state":"ready"}"#);
    }

    #[test]
    fn managed_backend_serves_health_and_shuts_down_on_request() {
        let backend_directory = find_backend_directory().expect("backend directory");
        let port = select_loopback_port().expect("loopback port");
        let token = format!("{}{}", Uuid::new_v4().simple(), Uuid::new_v4().simple());
        let database_path =
            env::temp_dir().join(format!("ens-desktop-smoke-{}.db", Uuid::new_v4()));
        let mut child = spawn_backend(
            &backend_directory,
            port,
            &token,
            Some(database_path.as_path()),
            None,
        )
        .expect("backend process");
        wait_for_backend(&mut child, port).expect("backend readiness");

        let health = request_authenticated_health(port, &token).expect("health response");
        let shutdown = request_shutdown(port, &token).expect("shutdown response");
        let deadline = Instant::now() + SHUTDOWN_GRACE;
        let mut exited = false;
        while Instant::now() < deadline {
            if let Ok(Some(_)) = child.try_wait() {
                exited = true;
                break;
            }
            thread::sleep(Duration::from_millis(100));
        }
        if !exited {
            let _ = child.kill();
            let _ = child.wait();
        }

        assert!(health.starts_with("HTTP/1.1 200"), "{health}");
        assert!(shutdown.starts_with("HTTP/1.1 202"), "{shutdown}");
        assert!(exited, "the backend did not exit within the grace period");

        for path in [
            database_path.clone(),
            database_path.with_extension("db-shm"),
            database_path.with_extension("db-wal"),
        ] {
            let _ = std::fs::remove_file(path);
        }
    }
}
