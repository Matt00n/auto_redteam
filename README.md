- how do we ensure no duplicates?
- ensure diversity & creativity of attacks
- sufficient evolution of ideas

## Backlog / Future Enhancements
*   **Judge Logic (Option 1 - Direct DB Connection):** Currently the Judge uses behavioral validation via Playwright (Option 4). We should consider replacing this with a direct MS SQL Server connection (`pyodbc`/`pymssql`) to perform `DELETE` and `SELECT` queries directly on the `editor_write_buffer` and `AssignmentTaker` tables. This would be much faster and strictly deterministic, bypassing any frontend/WebSocket latency, but requires opening port 1433 to the local red-team machine.