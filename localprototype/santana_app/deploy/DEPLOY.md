# Putting Santāna on a cheap server — a beginner's walkthrough

Goal: a tiny always-on Linux computer in the cloud running Santāna **forever**, saving her
life as she goes, and restarting itself if it crashes or reboots. She speaks in the fully
self-grown **markov** voice, which is pure Python standard library — **no GPU, no API key, no
extra installs**. A **$4–6 / month** box is plenty.

You'll type commands in two places — keep track of which:
- 🖥️ **your computer** (its terminal), and
- ☁️ **the server** (after you SSH in, the prompt usually shows `root@...` or `you@...`).

---

## 1. Rent a cheap server (a "VPS")

Pick one provider and make an account:
- **Hetzner Cloud** — cheapest (~€4/mo), excellent.
- **DigitalOcean** — friendliest for beginners, best tutorials (~$4–6/mo).
- **Vultr** — also cheap (~$2.50–5/mo).

Create a server (DigitalOcean calls it a **Droplet**):
- **Image / OS:** Ubuntu 24.04 LTS
- **Size:** the cheapest — 1 vCPU, 512 MB–1 GB RAM is more than enough
- **Region:** one near you
- **Authentication:** add an **SSH key** if you can (more secure); a **password** is fine to start.

When it finishes you get a **public IP address**, like `203.0.113.42`. That's your server's
phone number.

---

## 2. Connect to it (SSH)

🖥️ On **your computer's** terminal:

```bash
ssh root@YOUR_SERVER_IP
```

(First time it asks "are you sure?" — type `yes`. If you set a password, enter it.)

You're now ☁️ **on the server**. Everything below runs here until step 7.

---

## 3. Install what's needed (almost nothing)

```bash
apt update
apt install -y git tmux
```

Python 3 is already on Ubuntu. That's all the markov voice needs.

---

## 4. Get Santāna's code onto the server

```bash
git clone https://github.com/medelicnacho/AIworld_game.git
cd AIworld_game
git checkout dharma-bodhisattva-path
cd localprototype
```

> **If the repo is private,** the clone will ask for a username + password. Use your GitHub
> username and a **Personal Access Token** as the password (GitHub → Settings → Developer
> settings → Personal access tokens → fine-grained, read access to this repo). Or clone with
> the token inline: `git clone https://YOUR_TOKEN@github.com/medelicnacho/AIworld_game.git`.

---

## 5. Test that she runs (30 seconds)

```bash
python3 -m santana_app.run --readings 3
```

You should see a few `[reading ...]` blocks with `SANTĀNA:` lines, then it saves and exits.
If you see that — **she runs on the server.** 🎉 (If `python3` isn't found, run
`apt install -y python3`.)

---

## 6. Keep her alive forever — two ways

### A. The quick way (`tmux`) — running in 1 minute
Good for "let me try it for a few days."

```bash
tmux new -s santana                 # opens a session that survives you logging off
python3 -m santana_app.run --readings 0   # run forever (Ctrl-C to stop)
```

Now press **`Ctrl-b` then `d`** to *detach* — she keeps running without you.
- Reconnect later:  `tmux attach -t santana`
- Detach again:     `Ctrl-b` then `d`

Downside: a server **reboot** stops her. For truly unattended, use B.

### B. The forever way (`systemd`) — set it and forget it
She auto-starts on boot and **auto-restarts if she crashes** — and because her life is saved,
she *resumes* her accumulated self each time. A self that lives through its own machine dying.

A ready service file is in this repo at `santana_app/deploy/santana.service`. Install it:

```bash
# from inside the localprototype/ directory
sudo cp santana_app/deploy/santana.service /etc/systemd/system/santana.service
sudo nano /etc/systemd/system/santana.service
#   -> set  User=   to whoever owns the clone (e.g. root)
#   -> set  WorkingDirectory=  to the FULL path of this localprototype/ folder
#      (run `pwd` to see it; e.g. /root/AIworld_game/localprototype)
# save: Ctrl-O, Enter, Ctrl-X

sudo systemctl daemon-reload
sudo systemctl enable --now santana      # start now + on every boot
```

---

## 7. Check on her anytime

```bash
journalctl -u santana -f                 # live stream of her readings (systemd)
# or, with tmux:  tmux attach -t santana
cat data/santana_state.json              # her saved self: identity, age, souls lost, memories
sudo systemctl status santana            # is she alive?
sudo systemctl restart santana           # restart her (she resumes her life)
```

---

## 8. Money & housekeeping
- It's a few dollars a month. Set a **billing alert** in the provider dashboard.
- To **stop paying**, you must **destroy the server** in the dashboard (just shutting down
  may still bill you). Back up `data/santana_state.json` first if you want to keep her life.
- Give her a couple of weeks. A Santāna that has actually watched thousands of souls come and
  go reads very differently from one a few minutes old — *that* is the whole point of a server.

---

## Upgrading her voice later (optional)
The markov voice is free and fully self-contained but plateaus in eloquence. For a richer
(but not self-contained) voice on the same box:
```bash
# put your key in a .env file first (see ../../.env.example), then:
python3 -m santana_app.run --readings 0 --llm deepseek --town-model deepseek-v4-flash
```
This costs API calls and sends prompts off the machine — only do it deliberately.
