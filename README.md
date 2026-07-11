# Mind Frontier Studio v2.1

This patch fixes the FFmpeg concat-file error where `duration` was being joined to the image filename.

## Use it

1. Extract this ZIP into a new folder.
2. Copy your existing `.env` file from v2 into the new v2.1 folder.
3. Double-click `start.bat`.
4. Generate the video again.

The MP4 will be saved under:

`projects/<project-id>/mind-frontier-short.mp4`

Your earlier project folder may already contain the generated script, images, and narration. The failed render did not necessarily delete those files.
