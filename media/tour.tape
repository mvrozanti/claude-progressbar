Output media/tour.mp4
Output media/tour.gif

Set Shell "bash"
Set FontFamily "Iosevka Nerd Font Mono"
Set FontSize 18
Set Width 1280
Set Height 390
Set Padding 30
Set Theme "Catppuccin Mocha"
Set TypingSpeed 45ms

Hide
Type "export PS1='$ ' && clear"
Enter
Sleep 300ms
Show
Type "python3 scripts/demo.py --tour --cols 108"
Sleep 400ms
Enter
Sleep 36s
