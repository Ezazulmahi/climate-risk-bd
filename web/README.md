# web: Next.js frontend

Server-rendered pages that read from the FastAPI backend (`API_URL`, server-side only):

- `/`: outlook map, track-record summary and a card for every division
- `/city/[name]`: live forecast, past forecasts vs observed, SPI-3 history, city track record
- `/model`: test metrics, baselines, largest misses, limitations

```bash
npm install
```
```bash
npm run dev
```

See the root README for running the API and database.
