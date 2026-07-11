# Mind Frontier Studio v26 — Atlas Conversation

v26 adds a grounded conversational interface over Atlas data.

## Supported question types

- What should I make next?
- What are my best-performing videos?
- Why did my latest video underperform?
- Predict a video about a topic
- How accurate are Atlas predictions?
- Find evidence about a topic

## Grounding

Responses use:

- Atlas Memory
- YouTube Analytics
- Imported video data
- Prediction Engine
- Producer Workspace
- Strategy Agent

## API

- `POST /api/chat/ask`
- `GET /api/chat/conversations`
- `GET /api/chat/conversations/{conversation_id}`
- `POST /api/chat/clear`
