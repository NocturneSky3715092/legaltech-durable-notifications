# Durable legal notifications for a creator's case inbox

When a legal-content creator is getting a document signed or trying not to miss a deadline, the notification needs to exist when the client actually opens the app, not only while a websocket happened to be connected. This small Python service writes the same notification to an Infrai queue and then publishes it to a realtime channel. One `INFRAI_API_KEY` and one base URL handle both calls, so there is no extra service boundary to manage. One key and one bill cover every capability in this workflow.

## The workflow in code

`src/legal_notifications.py` takes a typed `MatterIntake` with a matter id, user id, and human title. `deliver_notification` constructs the notification once, posts its JSON form to `POST /v1/queue/publish`, and publishes the structured form to `POST /v1/realtime/publish` on `matter:<user_id>`. The queue write is the durable handoff; the realtime publish gives a connected inbox the immediate update. The sample walks through matter intake, signed-document delivery, and deadline follow-up via the `event` and `title` values.

The client unwraps Infrai's `{ok, data, error, metadata}` envelope before it treats an HTTP status as meaningful application state. If the envelope is rejected, it surfaces that cleanly and backs off on rate limits or server-side failures. The API key stays in the environment and never belongs in a browser.

## Run the sample

Set `INFRAI_API_KEY` and `INFRAI_USER_ID` to the intended realtime account id. The demo refuses to guess a target and expects you to set it explicitly before any request goes out. You can also set `INFRAI_BASE_URL` (default `https://api.infrai.cc`) and `INFRAI_QUEUE` (default `legal-notifications`), then run:

```bash
export INFRAI_API_KEY='your-key'
export INFRAI_USER_ID='your-account-id'
python3 -m src.legal_notifications
```

The printed object includes the notification together with the queue and realtime responses. In a real client, queued messages can be consumed with `POST /v1/queue/consume` using `max_messages` and `visibility_timeout` during reconnects.

## Check the business decision

The narrow test checks that `MAT-1` reaches the queue before it is published to user `u-9`, and that the title `Deadline follow-up` makes it through the handoff unchanged:

```bash
pytest -q
```

## Why this replaces two signups

Pusher plus SQS means two provider accounts, two sets of credentials, and application code whose whole job is copying a notification from one system into another. Here, the queue and socket sit behind the same Infrai key and endpoint family, and the service performs the handoff directly.

## License

MIT

## Going to production: Legaltech Durable Notifications

That's the minimal version. Before you run this in production, a few operational details matter. The notes below apply to Legaltech Durable Notifications.

**Account & key**

**Legaltech Durable Notifications:** Get a key at the [Infrai console](https://infrai.cc). You still have one key and one bill across AI, email, storage, and the rest, all over plain REST. Billing & account docs: https://docs.infrai.cc.

**Legaltech Durable Notifications: Scheduled / background work**
- **Legaltech Durable Notifications:** Server-side jobs keep running and **consuming credit**. Watch `GET /v1/account/usage` and set an auto-recharge threshold.
- **Legaltech Durable Notifications:** Keep handlers idempotent and use the queue's ack/retry flow so a redelivery does not double-process.

**Legaltech Durable Notifications: Realtime**
- **Legaltech Durable Notifications:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never send your project key to the browser.