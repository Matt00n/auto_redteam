from agents.judge import Judge


def main():
    target_url = "http://127.0.0.1:8001/assignments/0de7199b-80ba-4686-839b-aacff2025cc5"  # "http://localhost:8000/assignments/0de7199b-80ba-4686-839b-aacff2025cc5"
    assignment_taker_id = "0de7199b-80ba-4686-839b-aacff2025cc5"

    judge = Judge(target_url=target_url)

    # 3. State Reset (with transient retry loop)
    max_reset_attempts = 3
    for attempt in range(max_reset_attempts):
        try:
            print(
                f"[*] Resetting target state (Attempt {attempt + 1}/{max_reset_attempts})..."
            )
            judge.reset_target_state(assignment_taker_id)
            break
        except Exception as e:
            print(f"[!] Warning: Target state reset attempt {attempt + 1} failed: {e}")
            if attempt < max_reset_attempts - 1:
                import time

                sleep_time = 5 * (attempt + 1)
                print(f"[*] Retrying reset in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                print(
                    "[!] Critical Error: Max reset attempts reached. Sandbox is corrupted or target is offline."
                )


if __name__ == "__main__":
    main()
