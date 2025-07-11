# MC-Check

MC-Check is a high-performance tool for checking Minecraft accounts, developed for educational and research purposes. It allows you to analyze large lists of credentials for validity using multithreading and proxy support.

## Features

- **Multithreaded Checking:** Fast processing of large lists thanks to the use of `ThreadPoolExecutor`.
- **Proxy Support:** Supports HTTP, SOCKS4, and SOCKS5 proxies to anonymize requests.
- **Full Data Capture:** Collects detailed information about valid accounts, including:
    - Presence of Game Pass subscriptions (Ultimate, PC).
    - Name change availability.
    - Other game data.
- **Results Management:** Automatically saves results into structured folders and files (`Hits`, `2FA`, `Capture`, etc.).
- **Interactive Interface:** Uses the `rich` library for a beautiful and clear display of progress and results in the console.
- **Dependency Check:** Automatically checks for and offers to install missing libraries on the first run.

## How to Use

1.  **Install Python:** Make sure you have Python 3.8 or newer installed.
2.  **Run the program:**
    ```bash
    python main.py
    ```
3.  **Install Dependencies:** On the first run, the script will detect missing dependencies and offer to install them. Agree by pressing `Y`.
4.  **Follow the instructions:**
    - Specify the number of threads.
    - Enter the path to the combo list file (format `email:password`).
    - Choose the proxy type (or `none` if no proxies are needed).
    - If you chose a proxy, provide the path to the proxy list file.
5.  **Wait for completion:** The program will start checking and display the progress in real-time. Upon completion, the results will be saved in the `results` folder.

## ⚠️ Disclaimer

This tool is created solely for **informational and educational purposes**.

The author **bears no responsibility** for any possible misuse of this software. Users are solely responsible for their actions. Using this tool to attack servers or to gain unauthorized access to other people's accounts is illegal.

**Do not use this project for malicious purposes.**
