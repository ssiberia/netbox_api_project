# Chores Toolbox CLI

**Chores Toolbox** is a modular CLI application designed to automate the boring, repetitive, and daily tasks of an OPS engineer. 

Instead of running separate scripts, this tool provides a central, interactive **Main Menu** to access various submodules.

## Available Modules

### 1. NetBox IXP Peering Wizard (Active)
The first fully implemented module. It automates the provisioning of BGP peering sessions in **NetBox**, leveraging data directly from **PeeringDB**, and our NetBox via the API.

* **PeeringDB Integration:** Finds mutual exchange points based on ASN.
* **Smart IPAM Sync:**
    * Detects existing subnets in NetBox, and adds the remote IP address to the subnet with the correct tenant and description.
    * **Subnet Mirroring:** Auto-calculates the correct CIDR mask from the local IP.
* **BGP Session Creation:**
    * Links sessions to the correct Device and Site.
    * Populates **Custom Fields**: `prefix_limit`, `as_set` (intelligent selection), `md5` password, and so on.
    * **Sanitization:** Ensures strict alphanumeric naming for router compatibility.

### 2. More coming soon...
* *Placeholder for future modules (e.g., PNI setup)*

---

##  Installation

1.  **Clone the repository:**
    ```bash
    git clone git@gitlab.yourcompany.com:network-automation/chores-toolbox.git
    cd chores-toolbox
    ```

2.  **Create a Virtual Environment:**
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Configuration

Create a `.env` file in the root directory to store your credentials.
**⚠️ DO NOT commit this file to Git!**

```ini
# .env file content
NETBOX_URL=https://netbox.as5405.net
NETBOX_TOKEN=YOUR_KEY_HERE
```

## Usage

```bash
python main.py
```
Then just follow the wizard, it should be self-explanatory!