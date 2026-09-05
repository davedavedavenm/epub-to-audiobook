from __future__ import annotations

import sys
from kaggle.api.kaggle_api_extended import KaggleApi

def main():
    kernel = sys.argv[1] if len(sys.argv) > 1 else "davedavedavedavenm/breeze2-breakneck-audition"
    api = KaggleApi()
    api.authenticate()
    user, slug = kernel.split("/")
    status = api.kernels_status(kernel)
    print("STATUS:", status)
    
    # Try fetching log
    res = api.kernels_output_with_http_info(kernel)
    data = res[0]
    print("Keys in output:", data.keys() if hasattr(data, "keys") else dir(data))
    if hasattr(data, "log"):
        print("LOG TAIL:\n", (data.log or "")[-2000:])
    elif isinstance(data, dict) and "log" in data:
        print("LOG TAIL:\n", (data["log"] or "")[-2000:])

if __name__ == "__main__":
    main()
