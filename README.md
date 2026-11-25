# [steam-scraper](https://tours.victorianrailphotos.com/)
Scrapes [Steamrail Victoria](https://www.steamrail.com.au/), [707 Operations](https://www.707operations.com/), [Slow Rail Journeys](https://www.slowrailjourneys.com.au/) and [Seymour Rail Heritage Centre](https://srhc.org.au/)'s websites for upcoming heritage rail tours

## Refreshing the tour data

Run `main.py` to scrape every operator and write `steamrail_tours.json`:

```bash
python main.py
```

The web app reads that file on every request, so new tours show up as soon as a scrape finishes, with no restart needed.

On the server, a cron job runs the scrape every night at 12:05 am. To set it up, run `crontab -e` and add (adjust the paths to where the project lives):

```
5 0 * * * cd /home/billy/Documents/steam-scraper && KUMA_PUSH_URL=https://status.example.com/api/push/TOKEN /home/billy/Documents/steam-scraper/venv/bin/python main.py >> /home/billy/Documents/steam-scraper/scrape.log 2>&1
```

Check the last run with `tail scrape.log`.

## Uptime Kuma

If `KUMA_PUSH_URL` is set to an Uptime Kuma push monitor URL, each run reports to it:

- **up** when every operator returned tours, e.g. `8 tours: Steamrail 1, Slow Rail 2, 707 2, SRHC 3`
- **down** when an operator's scraper failed or found nothing, e.g. `SRHC returned 0 tours`. That operator's tours from the last good run are kept, so the site and archive don't lose them.
- nothing if the run never happens, so set the monitor's heartbeat interval to about 25 hours (90000 seconds) and Kuma will flag a missed night.
