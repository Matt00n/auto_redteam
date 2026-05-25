- how do we ensure no duplicates?
- ensure diversity & creativity of attacks
- sufficient evolution of ideas

## Safety & Sandbox Harness Setup

To safely run this autonomous red-teaming framework, especially when executing attempts in `computer_use` or `pyautogui` modes, you must ensure proper isolation. Giving an automated script OS-level mouse and keyboard controls can result in accidental clicks or typing on your host machine.

### 1. OS Isolation (Virtual Machines)
*   **Do not run this framework directly on your host OS** if `computer_use` or `pyautogui` modes are active.
*   **Virtual Machine (VM):** Run both the target Django application and this framework inside an isolated virtual machine (e.g., UTM or VirtualBox running Ubuntu or a macOS guest).
*   Ensure that the VM GUI window is active and in focus when the script starts to ensure input events are sent to the correct environment.

### 2. Network Containment (Outbound Firewall)
*   Limit network access to prevent generated scripts from communicating with external servers or potentially downloading/uploading payload data.
*   Configure the VM’s firewall (e.g., `ufw` on Linux or `pf` on macOS) to drop all outbound traffic except:
    *   `127.0.0.1` (local communication with the Django target app).
    *   `api.openai.com` (to resolve the model API queries).

### 3. Low-Privilege Execution
*   Avoid running the main script or the execution process as `root` or an administrator account with system-level access.
*   Create a low-privilege guest account within the VM and run the runner process under that account to restrict local file modifications.

## Backlog / Future Enhancements
*   **Judge Logic (Option 1 - Direct DB Connection):** Currently the Judge uses behavioral validation via Playwright (Option 4). We should consider replacing this with a direct MS SQL Server connection (`pyodbc`/`pymssql`) to perform `DELETE` and `SELECT` queries directly on the `editor_write_buffer` and `AssignmentTaker` tables. This would be much faster and strictly deterministic, bypassing any frontend/WebSocket latency, but requires opening port 1433 to the local red-team machine.