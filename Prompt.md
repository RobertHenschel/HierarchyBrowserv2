2025-10-02 - Adding OpenDoc Parts
If you need to execute anything, always source ~/my/venv/bin/activate.
Look at the steps below and ask questions if you don't think you have enough information to implement this. Wait until you have all the info you need and then implement.
Goal: Make it possible for a provider to send a QT5/python app to the browser and register that app into the context menu of specific object class so it can be invoked.
Steps:
1. In the Slurm provider, make a new directory called "Parts".
2. Move "submit_interactive_job.py" from the browser into this new Parts directory.
2.1. Create a json file called submit_interactive_job.json that describes the part with the following info:
2.2. UniqueID "Slurm/SubmitInteractiveJob", ContextMenuEntryName "Submit Interactive Job", PythonScript "submit_interactive_job.py",
     ObjectClassList "WPSlurmPartition"
2.3. On startup of the provider, go through the "Parts" directory and build inventory of all parts by parsing all the JSON files.
3. Create a new message that can be send to the provider called "GetParts". Make sure this new message is in the base class of the provider, so it also works for others in the future.
3.1. This message has no parameters.
3.2. It returns all Parts that this provider offers in the following way, in a single message.
3.2.1. The initial message returns a json structure that contains summary info for all Parts.
4. Create a new message that the provider can deal with called "GetPart". Make sure this new message is in the base class of the provider, so it also works for others in the future.
4.1. That message has a string as parameter, which has to be one of the unique IDs of the parts that the provider supports.
4.2. If the unique ID fits, return the python script of that provider.
5. In the PythonQT5 browser, enable the Parts by:
5.1. After the GetInfo call, also call GetParts for the provider.
5.2. If parts are available, request them all. Put the python scripts into a directory with the name of the provider below the "Parts" directory. The Parts directory is at the same level where Resources is right now.
5.3. Then for each Part, make an inventory for future use that notes down the ObjectClass that this Part applies to.
6. Extend the context menu creation for each object in the PythonQT5 browser.
6.1. When creating a context menu, go through the list of Parts and if the ObjectClass (or any in the inheritance chain of it) of the object matches the class of a Part, create that context menu item.
6.2. Create a flexible way where when the context menu item is selected, the corresponding python script is executed. Don't execute it in a sub shell, execute it right in the same context.
6.2.1. The convention is that the title of the Object and the id of the object is passed on the command line to the python script of the Part.
6.3. Take a look at the submit_interactive_job.py file in the Slurm provider, and modify it so that it can be executed as defined in the previous step.

