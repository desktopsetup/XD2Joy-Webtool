# XD2Joy Wired

An optional Windows app for the wired mode. 

pick which keyboard or mouse each Joy-Con should be. A PC with other keyboards or mice connected can still work on the PC, well the selected devices with the Wired app are sent only to the console. The .exe is just a python script running its tasks in the background so you can tab out of the Web-Tool and do other things well its running. The Web-Tool alone is more vulnerable to slip ups like having keystrokes still be sent to the PC and the console at the same time. The wired app helps prevent it.

You can run it from the source or install the .exe :

```
python -m pip install websockets
python xd2joy_helper.py
```

## What it does on your PC

- It reads keyboard and mouse input through Windows own interfaces, so the web tool can list your devices and send the picked ones to the boards.
- It only talks to the XD2Joy web tool when it starts it opens the web tool in your browser. It will ask for permission only when you select wired mode. If you are uncomfortable with this you can always just check the python script and run it locally in a terminal. 
- Holding the stop key "U" stops sending the input to the console and goes back to the PC.

## What it needs

- Windows 10 or 11, and Chrome
- XD2Joy boards on firmware with wired mode the web tool shows a Bluetooth / Wired switch for each Joy-Con when they have it, you can use a wired device and bluetooth device and mix and match.
