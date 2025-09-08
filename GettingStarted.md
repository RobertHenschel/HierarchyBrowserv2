

## Start the SLURM provider
- Connect to a login node of your HPC system and forward port 9123 from the login node to your local machine
  - For example, for an HPC called "Nautilus" it would look like this:
  - `ssh -L 9123:localhost:9123 nautilus.university.edu`
  - The above command will both forward the port and give you a shell on the machine.
- Now install the Slurm provider on the HPC login node.
  - In the SSH session from above, clone the Github repository
  - ` git clone git@github.com:RobertHenschel/HierarchyBrowserv2.git`
- Change into the directory of the SLURM provider
  - `cd HierarchyBrowserv2/providers/Slurm/`
- Create a python virtual environment and activate it
  - `python3 -m venv ./venv`
  - `source ./venv/bin/activate`
- Install required packages
  - `pip install -r ./requirements.txt`
- Run the Slurm provider
  - `./provider.py --port 9123`

## Start the browser
- On your local machine, install the browser.
  - Open a terminal and clone the repository
  - `git clone git@github.com:RobertHenschel/HierarchyBrowserv2.git`
Change ino the directory of the browser 
  - `cd HierarchyBrowserv2/browsers/PythonQT5/`
- Create a python virtual environment and activate it
  - `python3 -m venv ./venv`
  - `source ./venv/bin/activate`
- Install required packages
  - `pip install -r ./requirements.txt`
- Run the Slurm provider
  - `./browser.py --port 9123`

