@echo off
echo Updating translation templates...
xgettext --from-code=UTF-8 --language=Python --keyword=_ WritingToolApp.py -o pot_files/WritingToolApp.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/CustomPopupWindow.py -o pot_files/CustomPopupWindow.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/OnboardingWindow.py -o pot_files/OnboardingWindow.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/ResponseWindow.py -o pot_files/ResponseWindow.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/SettingsWindow.py -o pot_files/SettingsWindow.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/CommandsManagerDialog.py -o pot_files/CommandsManagerDialog.pot
xgettext --from-code=UTF-8 --language=Python --keyword=_ ui/CommandEditorDialog.py -o pot_files/CommandEditorDialog.pot

echo Merging templates...
msgcat pot_files/*.pot -o pot_files/merged.pot

echo Compiling translations...
msgfmt -o locales/vi/LC_MESSAGES/messages.mo locales/vi/LC_MESSAGES/messages.po
msgfmt -o locales/en/LC_MESSAGES/messages.mo locales/en/LC_MESSAGES/messages.po
msgfmt -o locales/it/LC_MESSAGES/messages.mo locales/it/LC_MESSAGES/messages.po
msgfmt -o locales/ja/LC_MESSAGES/messages.mo locales/ja/LC_MESSAGES/messages.po
msgfmt -o locales/zh/LC_MESSAGES/messages.mo locales/zh/LC_MESSAGES/messages.po

echo Done! Please restart the app.
pause
