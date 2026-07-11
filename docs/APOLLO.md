# Project Apollo

Apollo is Mind Frontier Studio's persistent batch-production layer.

## Capabilities

- Plans queues of 1–10 videos
- Uses Orion planning and Atlas evidence
- Renders sequentially to avoid concurrent API and FFmpeg overload
- Supports pause and resume
- Records completed, failed and remaining items
- Refreshes Dashboard and Atlas after a batch run
- Provides a CLI runner for unattended production

## CLI

```powershell
python .\run_apollo_queue.py apollo-QUEUE_ID --max-items 10
```

## Storage

`studio_memory/apollo-queues/`

## Safety and cost control

Apollo never starts rendering when a queue is created. Rendering begins only after
the user explicitly selects Run Next, Run Next 3, or launches the CLI runner.
