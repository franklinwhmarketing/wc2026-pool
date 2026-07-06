#!/usr/bin/env python3
"""
FranklinWH World Cup 2026 Pool — Results Scraper
Fetches completed match results from ESPN's public API and writes results.json.
Run daily: python3 fetch_results.py
"""

import requests
import json
import sys
from datetime import date, timedelta

# ESPN team abbreviation → pool code
ABBR_MAP = {
    'ARG': 'ARG', 'BRA': 'BRA', 'ENG': 'ENG', 'FRA': 'FRA', 'ESP': 'ESP',
    'BEL': 'BEL', 'GER': 'GER', 'NED': 'NED', 'NOR': 'NOR', 'POR': 'POR',
    'COL': 'COL', 'CRO': 'CRO', 'JPN': 'JPN', 'MEX': 'MEX', 'MAR': 'MAR',
    'SUI': 'SUI', 'URU': 'URU', 'USA': 'USA',
    'AUT': 'AUT', 'BIH': 'BIH', 'CAN': 'CAN', 'CZE': 'CZE', 'ECU': 'ECU',
    'EGY': 'EGY', 'CIV': 'CIV', 'IVC': 'CIV', 'PAR': 'PAR', 'SCO': 'SCO',
    'SEN': 'SEN', 'SWE': 'SWE', 'TUR': 'TUR',
    'ALG': 'ALG', 'AUS': 'AUS', 'CPV': 'CPV', 'CV':  'CPV',
    'CUW': 'CUW', 'CUR': 'CUW',
    'COD': 'COD', 'DRC': 'COD', 'RDC': 'COD',
    'GHA': 'GHA', 'HAI': 'HAI',
    'IRN': 'IRN', 'IRI': 'IRN', 'IRQ': 'IRQ',
    'JOR': 'JOR', 'NZL': 'NZL', 'PAN': 'PAN', 'QAT': 'QAT',
    'KSA': 'KSA', 'SAU': 'KSA',
    'RSA': 'RSA', 'SAF': 'RSA',
    'KOR': 'KOR', 'SKO': 'KOR',
    'TUN': 'TUN', 'UZB': 'UZB',
}

# ESPN team display name → pool code (fallback if abbreviation doesn't match)
NAME_MAP = {
    'argentina': 'ARG', 'brazil': 'BRA', 'england': 'ENG',
    'france': 'FRA', 'spain': 'ESP', 'belgium': 'BEL',
    'germany': 'GER', 'netherlands': 'NED', 'norway': 'NOR',
    'portugal': 'POR', 'colombia': 'COL', 'croatia': 'CRO',
    'japan': 'JPN', 'mexico': 'MEX', 'morocco': 'MAR',
    'switzerland': 'SUI', 'uruguay': 'URU',
    'united states': 'USA', 'usa': 'USA', 'us': 'USA',
    'austria': 'AUT', 'bosnia and herzegovina': 'BIH',
    'bosnia & herzegovina': 'BIH', 'canada': 'CAN',
    'czech republic': 'CZE', 'czechia': 'CZE', 'ecuador': 'ECU',
    'egypt': 'EGY', "ivory coast": 'CIV', "côte d'ivoire": 'CIV',
    "cote d'ivoire": 'CIV', 'paraguay': 'PAR', 'scotland': 'SCO',
    'senegal': 'SEN', 'sweden': 'SWE', 'turkiye': 'TUR', 'turkey': 'TUR',
    'algeria': 'ALG', 'australia': 'AUS', 'cape verde': 'CPV',
    'curaçao': 'CUW', 'curacao': 'CUW',
    'dr congo': 'COD', 'congo dr': 'COD', 'democratic republic of congo': 'COD',
    'ghana': 'GHA', 'haiti': 'HAI', 'iran': 'IRN', 'iraq': 'IRQ',
    'jordan': 'JOR', 'new zealand': 'NZL', 'panama': 'PAN',
    'qatar': 'QAT', 'saudi arabia': 'KSA', 'south africa': 'RSA',
    'south korea': 'KOR', 'korea republic': 'KOR', 'republic of korea': 'KOR',
    'tunisia': 'TUN', 'uzbekistan': 'UZB',
}

# Group stage ends June 26; knockouts begin June 29
KNOCKOUT_START = date(2026, 6, 29)
TOURNAMENT_START = date(2026, 6, 11)
TOURNAMENT_END = date(2026, 7, 19)

# Teams that have advanced to the knockout stage (Round of 32).
# Derived from ESPN standings after group stage completes.
# Updated automatically by fetch_standings(); fallback list used if API fails.
KNOWN_ADVANCED = set()  # populated at runtime

# Teams confirmed eliminated where ESPN API didn't log the knockout game.
# Add codes here when ESPN has a data gap (e.g. RSA lost to CAN in R32 but no game record exists).
MANUAL_ELIMINATED = {'RSA'}


def resolve_team(abbr, name):
    code = ABBR_MAP.get(abbr.upper())
    if code:
        return code
    code = NAME_MAP.get(name.lower())
    if code:
        return code
    # Partial name match
    name_lower = name.lower()
    for k, v in NAME_MAP.items():
        if k in name_lower or name_lower in k:
            return v
    return None


def fetch_standings():
    """
    Fetch group standings from ESPN to determine which teams are eliminated.
    Returns a set of eliminated team codes (definitely out = finished 4th in group).
    Also updates KNOWN_ADVANCED with confirmed group-stage advancers.
    """
    url = 'https://site.api.espn.com/apis/v2/sports/soccer/fifa.world/standings'
    try:
        r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f'  Warning: standings fetch failed — {e}', file=sys.stderr)
        return set()

    eliminated = set()
    # ESPN standings structure: data['children'] is a list of groups
    groups = data.get('children', [])
    for group in groups:
        entries = (group.get('standings') or {}).get('entries', [])
        if not entries:
            continue
        # Each entry has a 'stats' list; find the 'rank' stat
        def get_rank(entry):
            for s in entry.get('stats', []):
                if s.get('name') == 'rank':
                    return int(s.get('value', 99))
            return 99

        sorted_entries = sorted(entries, key=get_rank)

        for entry in entries:
            team = entry.get('team', {})
            abbr = team.get('abbreviation', '')
            name = team.get('displayName', team.get('shortDisplayName', ''))
            code = resolve_team(abbr, name)
            if not code:
                continue
            stats = {s['name']: s.get('value') for s in entry.get('stats', [])}
            advanced = stats.get('advanced')
            if advanced == 0.0:
                eliminated.add(code)
            elif advanced == 1.0:
                KNOWN_ADVANCED.add(code)

    return eliminated


def fetch_day(d):
    date_str = d.strftime('%Y%m%d')
    url = f'https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard?dates={date_str}'
    try:
        r = requests.get(url, timeout=8, headers={'User-Agent': 'Mozilla/5.0'})
        r.raise_for_status()
        return r.json().get('events', [])
    except Exception as e:
        print(f'  Warning: could not fetch {date_str} — {e}', file=sys.stderr)
        return []


def main():
    today = min(date.today(), TOURNAMENT_END)
    if today < TOURNAMENT_START:
        print('Tournament has not started yet.')
        return

    # Fetch standings to determine eliminated teams (only meaningful after group stage)
    eliminated = set()
    if date.today() >= KNOCKOUT_START:
        eliminated = fetch_standings()

    results = {}  # code → {wins, draws}
    knockout_wins = {}  # code → knockout wins only (used to compute remaining games)
    total_matches = 0
    total_goals = 0
    total_red_cards = 0
    match_log = []

    d = TOURNAMENT_START
    while d <= today:
        events = fetch_day(d)
        is_knockout = d >= KNOCKOUT_START

        for event in events:
            competition = (event.get('competitions') or [{}])[0]
            status = competition.get('status', {}).get('type', {})

            # Only process completed matches
            if not status.get('completed', False):
                continue

            competitors = competition.get('competitors', [])
            if len(competitors) != 2:
                continue

            parsed = []
            for c in competitors:
                team = c.get('team', {})
                abbr = team.get('abbreviation', '')
                name = team.get('displayName', team.get('shortDisplayName', ''))
                try:
                    score = int(c.get('score', '0'))
                except (ValueError, TypeError):
                    score = 0
                winner = c.get('winner', False)
                code = resolve_team(abbr, name)
                parsed.append({'code': code, 'abbr': abbr, 'name': name, 'score': score, 'winner': winner})

            a, b = parsed[0], parsed[1]

            # Ensure both teams exist in results
            for p in [a, b]:
                if p['code'] and p['code'] not in results:
                    results[p['code']] = {'wins': 0, 'draws': 0}

            log_entry = f"{d} | {a['name']} {a['score']}–{b['score']} {b['name']}"

            if a['score'] == b['score'] and not is_knockout:
                # Group stage draw
                if a['code']:
                    results[a['code']]['draws'] += 1
                if b['code']:
                    results[b['code']]['draws'] += 1
                log_entry += ' [DRAW]'
            elif a['score'] > b['score'] or (a['score'] == b['score'] and a.get('winner')):
                if a['code']:
                    results[a['code']]['wins'] += 1
                if is_knockout and a['code']:
                    knockout_wins[a['code']] = knockout_wins.get(a['code'], 0) + 1
                if is_knockout and b['code']:
                    eliminated.add(b['code'])  # loser exits tournament
                log_entry += f" [WIN: {a['name']}]"
            elif b['score'] > a['score'] or (a['score'] == b['score'] and b.get('winner')):
                if b['code']:
                    results[b['code']]['wins'] += 1
                if is_knockout and b['code']:
                    knockout_wins[b['code']] = knockout_wins.get(b['code'], 0) + 1
                if is_knockout and a['code']:
                    eliminated.add(a['code'])  # loser exits tournament
                log_entry += f" [WIN: {b['name']}]"

            # Goals
            total_goals += a['score'] + b['score']

            # Red cards from competition details (ESPN sets an explicit flag)
            for detail in competition.get('details', []):
                if detail.get('redCard') is True:
                    total_red_cards += 1

            match_log.append(log_entry)
            total_matches += 1

        d += timedelta(days=1)

    # Print match log
    print(f'\nProcessed {total_matches} completed matches:\n')
    for entry in match_log:
        print(' ', entry)

    # Apply manual overrides for teams ESPN API missed
    eliminated |= MANUAL_ELIMINATED

    # Compute remaining_wins per live team.
    # A team that survived groups starts with 5 possible knockout wins (R32→R16→QF→SF→Final).
    # Each knockout win they've already recorded reduces that by 1.
    remaining_wins = {}
    for code in results:
        if code in eliminated:
            remaining_wins[code] = 0
        else:
            remaining_wins[code] = max(0, 5 - knockout_wins.get(code, 0))

    # Write results.json
    output = {
        'results': results,
        'eliminated': sorted(eliminated),
        'remaining_wins': remaining_wins,
        'updated': today.isoformat(),
        'matches_processed': total_matches,
        'total_goals': total_goals,
        'total_red_cards': total_red_cards,
    }
    out_path = 'results.json'
    with open(out_path, 'w') as f:
        json.dump(output, f, indent=2)

    print(f'\nWrote {out_path} with {len(results)} teams.')


if __name__ == '__main__':
    main()
