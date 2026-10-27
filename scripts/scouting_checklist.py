"""Sport/stat research coverage for qualitative Engine B; no invented metrics."""
CORE={
 'NFL':('deployment_trends','team_volume','opponent_scheme','defensive_funnel','game_environment'),
 'NBA':('deployment_trends','minutes_usage','pace_possessions','opponent_scheme','rotation_injuries','game_environment'),
 'NHL':('deployment_trends','toi_lines','special_teams','opponent_style','game_environment'),
}
DETAILS={
 'deployment_trends':'Compare recent deployment and opportunity with season/role windows; distinguish changed role from noisy scoring streaks.',
 'team_volume':'Pass attempts, neutral-situation pass rate, pace, plays and expected script; targets are not pass attempts.',
 'opponent_scheme':'Opponent scheme and player-specific mechanism, not only a team ranking.',
 'defensive_funnel':'Which positions/alignments receive opportunities and why; adjust for personnel and schedule.',
 'game_environment':'Spread, total, weather, rest and competitive/blowout scenarios relevant to the prop.',
 'targets_routes':'Targets, target share, routes, route participation and targets per route; note denominators and sample windows.',
 'passer_progression':'First-read, secondary-read and checkdown tendencies, pressured reads and QB changes. Partial buckets do not equal total production.',
 'coverage_matchup':'Man/zone, coverage shells and likely assignments, with player splits and sample limitations.',
 'target_depth_alignment':'aDOT/air yards, slot/wide/backfield deployment and route/coverage interaction.',
 'pressure_protection':'Pressure generation, protection personnel, time available and sacks/scrambles versus pass attempts.',
 'receiver_availability':'Availability and redistribution among actual route participants, not nominal depth-chart rank.',
 'rush_share':'Carries, snap role, rushing share, goal-line role only as relevant to covered rushing stats.',
 'run_front':'Box counts, front structure, gap/zone fit and opponent run distribution.',
 'blocking_personnel':'Offensive line, blocking style and injury changes; distinguish evidence from expectation.',
 'defensive_alignment':'Defensive snap share, position/alignment and competition for tackle opportunities.',
 'opponent_play_distribution':'Run/pass mix, expected plays and target depth that reach this defender.',
 'tackle_funnel':'Tackle opportunities by position, scorer/venue effects if sourced, and teammate competition.',
 'minutes_usage':'Minutes, starts, rotation, usage, touches and role changes; connect them to the chosen stat.',
 'pace_possessions':'Possessions, pace and transition opportunity with compatible units.',
 'rotation_injuries':'Active rotation, absences, replacement responsibilities and expected minutes uncertainty.',
 'shot_profile_matchup':'Attempts, rim/midrange/three-point locations, free-throw opportunity and opponent shot concessions.',
 'defender_assignment':'Likely defender, help rules, switching/drop/zone and lineup-specific matchup.',
 'touches_creation':'Touches, on-ball/off-ball creation, drives and possession role.',
 'potential_assists':'Potential assists, passes, time of possession and teammate availability; do not equate potential assists to assists.',
 'teammate_conversion':'Teammate shot profile/conversion and likely lineups affecting assist realization.',
 'rebound_opportunities':'Rebound chances, contested share, available misses and minutes/lineup exposure.',
 'rebounding_matchup':'Opponent shot locations, frontcourt sizes, box-outs and defensive/offensive rebound roles.',
 'three_point_attempts':'Three-point attempt volume and catch-and-shoot versus pull-up role.',
 'three_point_location_matchup':'Corner/above-break concessions, closeouts and likely assignment.',
 'toi_lines':'Time on ice, line/pair combinations and current deployment uncertainty.',
 'special_teams':'Power-play/penalty-kill unit and ice time, opponent penalty exposure and role.',
 'opponent_style':'Possession/forecheck style, zone time, matchups and personnel affecting this stat.',
 'shot_attempts_rates':'Shot attempts, individual SOG/60, conversion to on-target shots, recent deployment and shot location.',
 'line_matching':'Likely opposing line/pair and home last-change effects when verified.',
 'shot_suppression':'Opponent attempts/shots allowed by situation and role-specific shot access.',
 'opponent_attempt_volume':'Opponent attempts, point-shot volume and offensive-zone exposure.',
 'defensive_deployment':'Defensive-zone starts, pairing, penalty kill and time defending.',
 'shot_lane_matchup':'Shooter locations and blocking lanes; team attempts are not individual blocks.',
 'opponent_shot_volume':'Opponent SOG generation and expected goalie workload across script scenarios.',
 'expected_starter':'Confirmed starter and expected game participation; no backup-goalie assumption.',
 'shot_quality_defense':'Team suppression, shot quality and save opportunity; xG is not shots or saves.',
}


def required_checks(sport,stat):
 sport=str(sport or '').upper();stat=str(stat or '').lower()
 checks=list(CORE.get(sport,()))
 if sport=='NFL':
  if stat in ('receptions','receiving yards'):
   checks+=['targets_routes','passer_progression','coverage_matchup','target_depth_alignment']
  elif stat in ('passing yards','pass attempts','completions'):
   checks+=['passer_progression','pressure_protection','coverage_matchup','receiver_availability']
  elif stat in ('rushing yards','rush attempts'):
   checks+=['rush_share','run_front','blocking_personnel']
  elif stat in ('tackles','tackles + assists'):
   checks+=['defensive_alignment','opponent_play_distribution','tackle_funnel']
 elif sport=='NBA':
  parts={'pra':{'points','rebounds','assists'},'pr':{'points','rebounds'},
         'pa':{'points','assists'},'ra':{'rebounds','assists'}}.get(stat,{stat})
  if parts & {'points','threes'}:checks+=['shot_profile_matchup','defender_assignment','touches_creation']
  if 'assists' in parts:checks+=['potential_assists','teammate_conversion']
  if 'rebounds' in parts:checks+=['rebound_opportunities','rebounding_matchup']
  if 'threes' in parts:checks+=['three_point_attempts','three_point_location_matchup']
 elif sport=='NHL':
  if stat=='shots on goal':checks+=['shot_attempts_rates','line_matching','shot_suppression']
  elif stat=='blocked shots':checks+=['opponent_attempt_volume','defensive_deployment','shot_lane_matchup']
  elif stat in ('saves','goalie saves'):checks+=['opponent_shot_volume','expected_starter','shot_quality_defense']
 return checks


def seed(sport,stat,row=None):
 return {'evidence':{k:None for k in ('matchup','opportunity','injuries','game_script')},
         'supporting_stats':{k:None for k in required_checks(sport,stat)},
         'research_instructions':{k:DETAILS[k] for k in required_checks(sport,stat)},
         'scenarios':[],
         'unverified_feed_diagnostics':{k:(row or {}).get(k) for k in (
             'baseline_workload','workload_tonight','pace_per_game','pace_ratio','possessions',
             'shots_against_per_game','shots_against_ratio','snap_share','target_share',
             'routes_per_game','route_share','offense_snaps_per_game','defense_snaps_per_game',
             'first_read_target_share','checkdown_target_share','qb_first_read_rate',
             'qb_checkdown_tendency','def_forced_checkdown_rate',
             'def_first_read_suppression_rate','def_rb_target_funnel_share')
             if (row or {}).get(k) is not None},
         'diagnostic_source':(row or {}).get('source_url')}
