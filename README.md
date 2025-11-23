# CleanMail

A tool to quickly clean up your email inbox!

forked from BharatKalluri/cleanmail.

## Features

Connect with a mailserver through IMAP

1) Inbox Cleanup: group/count messages by sender, provide unsubscribe link and group delete.
2) Folder Pruning: show messagecount per folder, prune old messages to trashbin or to archive
3) Trash Bin: Empty the trashbin

## running the application

This is a python application that is setup to run using the uv package manager.

1. Make sure Python and uv are installed and clone the repository.
2. Run the application:
```sh
uv run start
```
The applicaition is available in a newly opened webbrowser window.

## Project history

- start with fork from BharatKalluri/cleanmail
- Implemented a security recomendation to validate email address, preventing undesired injection of ALL.
- Changed the system to work with any Imap server, not limited to yahoo or google
- Added ability to save server/mailaddress and pwd
- add feature to prune folder (delete messages older than ...)
- added feature to prune to archive (as alternative to prune to deleted items)