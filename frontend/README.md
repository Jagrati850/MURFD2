# Health Access Voice Agent — Frontend (Days 1 to 8)

Next.js frontend for the **Health Access Voice Agent**, featuring a 3D Dark Orb visualizer, Live Transcript panel, and an interactive **Day 8 Call Analytics Dashboard**.

## Key Features
- **3D Dark Orb Visualizer**: Real-time 3D audio reactivity powered by WebGL/ShaderToy.
- **5 Agent States**: Visual state feedback (*Ready*, *Connecting*, *Listening*, *Speaking*, *Ended*).
- **Day 8 Call Analytics Dashboard**: Live metrics for Total Calls, Success Rate %, Failed Calls, Escalated Calls (Day 7), and SQLite Call History table.
- **Live Health Data Panel**: Displays real-time fetched facility lookups, heat/AQI advisories, and triage urgency badges via LiveKit data channel.

## Running Locally

```bash
pnpm install
pnpm dev
```

Open `http://localhost:3000`.
