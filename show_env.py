import os

for k, v in os.environ.items():
    if "POWERCORD" in k:
        print(f"{k} = {v}")
