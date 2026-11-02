# Using the app from your phone

Your phone opens the app in its browser while your PC runs it. The phone shows the app; your leads, drafts and AI stay on the PC. The connection goes through Tailscale, a free private network between your own devices, so it works at home and on mobile data. Design and security: ADR-025.

## What you need

- The PC switched on, not asleep, with Etch N Shine open.
- Tailscale on the PC and on the phone, signed in to the **same** Tailscale account. The free Personal plan is enough.

## Set up (once)

1. **Install Tailscale on the PC** from <https://tailscale.com/download/windows> and sign in.
2. **Install Tailscale on the phone** from the App Store or Google Play and sign in to the same account. Leave it switched on.
3. In the app on the PC, open **Settings → Phone access** and tick **Allow paired phones to connect**.
4. Under **Phone address**, choose **Set up phone address**. If Tailscale says HTTPS must be switched on for your account first, choose **Open Tailscale settings**, allow HTTPS certificates, then try again. When it's done, the panel shows the address, for example `https://your-pc.tail1a2b.ts.net/`.
5. Choose **Pair a phone**. A QR code and an 8-character code appear for 5 minutes.
6. On the phone, scan the QR code with the camera. The pairing page opens with the code filled in. Give the phone a name and tap **Pair**.
7. To open it like an app: in Safari tap **Share → Add to Home Screen**; in Chrome on Android tap **⋮ → Add to Home screen**.

The phone stays signed in. If it isn't used for 30 days it has to be paired again.

## Every day

- Open the phone address (or the home-screen icon). **Today**, **Shortlist**, **Pipeline** and **Drafts** are along the bottom; everything else is under **More**.
- When the phone is waiting for the PC, a small "Saving on your PC…", "Working on your PC…" or "Thinking on your PC…" message appears at the bottom. If it takes more than 10 seconds it says that the PC carries on, so you can leave the screen.
- **Sending an approved email:** open the draft, tap **Open in mail to send**. Your phone's mail app opens with the message. Set Zoho Mail as the phone's default mail app if you want it to open there. Send it, come back, and answer **Did you send it?** with **Yes, sent**. It's only recorded as sent when you say so.
- **AI:** the assistant runs on the PC with the same model and limits as on the desktop. If you lock the phone while it's thinking, the answer still arrives; the phone picks it up when you come back.

## What stays on the PC

Connections and keys (Meta, Google Places, cloud polish), backups and restore, lead export, deleting a lead's data, campaign defaults and limits, scoring settings, pairing phones, and changes to products and templates. On the phone, Catalogue and Templates are view only.

## If something goes wrong

| What you see on the phone | What to do |
|---|---|
| "Your PC isn't reachable" | Check the PC is on and awake, Etch N Shine is open, and Tailscale is signed in on both. Then tap **Try again**. |
| "Pair this phone" when it used to work | The phone was removed on the PC, or wasn't used for 30 days. Pair it again from **Settings → Phone access** on the PC. |
| "That code doesn't match" | Check the code on the PC. After 5 wrong tries the code is cancelled; show a new one. |
| "The phone app files aren't built" | Restart the app with **Start Etch N Shine.cmd**, which rebuilds them. Or run `npm run frontend:build`. |
| Settings on the PC says "Port 8770 is already in use" | Another program uses that port. Close it and switch phone access off and on, or set `ENS_MOBILE_GATEWAY_PORT` to another port and set up the phone address again. |

**Keep the PC awake:** Windows Settings → System → Power → *When plugged in, put my device to sleep after* → **Never**, or a long time.

## If a phone is lost or stolen

1. On the PC: **Settings → Phone access → Remove** next to that phone. It is locked out at once. **Remove all phones** is there too.
2. Optionally remove the phone from your Tailscale account at <https://login.tailscale.com/admin/machines>.
3. Turn on two-step sign-in for your Tailscale account if it isn't on.

## Switching it all off

Untick **Allow paired phones to connect** in Settings → Phone access. Phones disconnect immediately. To remove the address as well, choose **Remove phone address**.

## Technical notes

- The phone gateway listens on `127.0.0.1:8770` only. `tailscale serve` forwards `https://<pc>.ts.net` to it; nothing in the app listens on the network.
- Gateway activity is logged as `mobile_*` events (gateway started and stopped, pairing, revocation, rejected requests) in the app's log folder. Codes, cookies and secrets are never logged.
- Changes made from a phone are recorded in the audit log as `phone:<device id>` and show "from your phone" in lead history.
