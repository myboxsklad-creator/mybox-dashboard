name: Update Dashboard Daily

on:
  schedule:
    - cron: '0 17 * * *'  # 20:00 Kyiv (UTC+3)
  workflow_dispatch:       # ручний запуск кнопкою

permissions:
  contents: write          # дозвіл на запис в репо

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout repo
        uses: actions/checkout@v4
        with:
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Update dashboard data
        run: python update_dashboard.py

      - name: Commit and push if changed
        run: |
          git config user.name "mybox-bot"
          git config user.email "bot@mybox.ua"
          git add index.html
          git diff --staged --quiet || git commit -m "Auto-update: $(date '+%d.%m.%Y %H:%M') Kyiv"
          git push
