use serde::Serialize;
use std::{
    env,
    io::{Read, Write},
    net::{TcpListener, TcpStream},
    path::{Path, PathBuf},
    process::{Child, Command, Stdio},
    sync::Mutex,
    thread,
    time::Duration,
};
use tauri::{Manager, RunEvent, State};
use uuid::Uuid;

#[derive(Clone, Serialize)]
#[serde(rename_all = "camelCase")]
struct BackendConnection {
    base_url: String,
    session_token: String,
}

struct BackendRuntime {
    connection: BackendConnection,
    child: Mutex<Option<Child>>,
}

impl BackendRuntime {
    fn stop(&self) {
        if let Ok(mut guard) = self.child.lock() {
            if let Some(mut child) = guard.take() {
                let _ = child.kill();
                let _ = child.wait();
            }
        }
    }
}

#[tauri::command]
fn backend_connection(state: State<'_, BackendRuntime>) -> BackendConnection {
    state.connection.clone()
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
) -> Result<Child, String> {
    let python = find_python(backend_directory);
    let mut command = Command::new(python);
    command
        .args(["-m", "app.cli", "serve"])
        .current_dir(backend_directory)
        .env("ENS_HOST", "127.0.0.1")
        .env("ENS_PORT", port.to_string())
        .env("ENS_SESSION_TOKEN", token)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
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
) -> Result<Child, String> {
    let mut command = Command::new(executable);
    command
        .arg("serve")
        .env("ENS_HOST", "127.0.0.1")
        .env("ENS_PORT", port.to_string())
        .env("ENS_SESSION_TOKEN", token)
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
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

fn request_authenticated_health(port: u16, token: &str) -> Result<String, String> {
    let mut stream = TcpStream::connect(("127.0.0.1", port)).map_err(|error| error.to_string())?;
    let request = format!(
        "GET /api/v1/health HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Session-Token: {token}\r\nConnection: close\r\n\r\n"
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
    let mut child =
        spawn_packaged_backend(&executable, port, &token, Some(runtime_directory.as_path()))?;
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

fn wait_for_backend(child: &mut Child, port: u16) -> Result<(), String> {
    for _ in 0..100 {
        if TcpStream::connect(("127.0.0.1", port)).is_ok() {
            return Ok(());
        }
        if let Some(status) = child.try_wait().map_err(|error| error.to_string())? {
            return Err(format!(
                "Backend exited during startup with status {status}"
            ));
        }
        thread::sleep(Duration::from_millis(100));
    }
    Err("Backend did not become ready within 10 seconds".to_string())
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
            let mut child = if cfg!(debug_assertions) {
                let backend_directory = find_backend_directory()?;
                spawn_backend(&backend_directory, port, &token, None)?
            } else if let Some(executable) = packaged_backend_path(application) {
                spawn_packaged_backend(&executable, port, &token, None)?
            } else {
                return Err("Packaged backend resource was not found.".into());
            };
            if let Err(error) = wait_for_backend(&mut child, port) {
                let _ = child.kill();
                return Err(error.into());
            }
            application.manage(BackendRuntime {
                connection: BackendConnection {
                    base_url: format!("http://127.0.0.1:{port}/api/v1"),
                    session_token: token,
                },
                child: Mutex::new(Some(child)),
            });
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![backend_connection])
        .build(tauri::generate_context!())
        .expect("failed to build Etch 'N' Shine desktop application");

    app.run(|handle, event| {
        if matches!(event, RunEvent::Exit | RunEvent::ExitRequested { .. }) {
            handle.state::<BackendRuntime>().stop();
        }
    });
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn managed_backend_serves_authenticated_health_on_loopback() {
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
        )
        .expect("backend process");
        wait_for_backend(&mut child, port).expect("backend readiness");

        let response = request_authenticated_health(port, &token).expect("health response");

        let _ = child.kill();
        let _ = child.wait();
        assert!(response.starts_with("HTTP/1.1 200"), "{response}");

        for path in [
            database_path.clone(),
            database_path.with_extension("db-shm"),
            database_path.with_extension("db-wal"),
        ] {
            let _ = std::fs::remove_file(path);
        }
    }
}
