


To install:

```sh
# Clone the repo
sudo apt install git
git clone https://github.com/coderforlife/lego-lcd.git
cd lego-lcd

# Create a virtual environment
python3 -m venv venv
. venv/bin/activate

# Install the dependencies and the application itself
bash install-deps.sh
pip install -e .

# Install, enabled, and run the service
sudo cp lcd-clock.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now lcd-clock.service
```
