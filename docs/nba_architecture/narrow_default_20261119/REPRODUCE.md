# Default subset profile reproduction

Accepted explicit useramendment479b8570; final implementationdb1c43a56b3e0f69d3e47f900827fa9ec7689030.
Config config/nba_research_profile.json; defaultentrypoint scripts/nba_research.py.

```sh
python -m unittest tests.nba_architecture.test_research_profile_v1 -v
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 PYTHONPATH=.:tests/nba_architecture python -m unittest discover -s tests/nba_architecture -v
python scripts/nba_research.py --capture-dir docs/nba_architecture/p1_overnight_20261119/raw/pregame-20261118T234000059565Z-aae5f441 --cohort docs/nba_architecture/p1_prospective_20261118/COHORT.json --output /tmp/nba-subset-research-requests.json
sha256sum -c docs/nba_architecture/narrow_default_20261119/SHA256SUMS
```

Output path must not already exist; CLI is create-only. Oldsourcebytes andclocks
are actually capturedprefreeze; this is their researchrequest replay, not an
original historicalforecast. No fit/modelwas supplied, hence0probability outputs.
36allcandidates =26conditional-source-ready requests +10sourceabstentions
(9reportedOut and1capturedrosterdisagreement). Everyrow retained. Legalpopulation
countnull. Unknowneligibility/q staynull; no fullActiveList prerequisite.

Readinessmeans sourceidentity/actualclock/byteconsistency suitable for a research
request, not sourceauthenticity/modeladmission or successfulforecast. Reported
sourceActive or omittedinjuryentry never becomes positive participation. Optional
nativeNBAroster namecorroboration is not an externalIDcrosswalk/eligibilitygrant.
Absentwholeteam/sourcebad clocks/wrongteam/duplicate/invalidmembers produce
localabstentions or an explicitunknownmissingpopulation, while validotherscontinue.
Badglobalgame/start/schedule blocks all affectedrows without deletingthem.

ActualCLI stdout/stderr and perrowoutput underowner/. Firstmissing-source crash
and independentoptionalcorruption red are retained alongside fixes. Positive/
mutationcontrols are engineeringchecks with actualsource-derivedfixtures, not
admissions of resealedmutantdata. Exactsource/receipt/rawbody hash domains remain
separate. Top SHA256SUMS covers exactfilebytes including configuration/defaultdocs.

README/AGENTS/gateboundary now pointto active useramendment; oldfrozenfullgates
remainhistorical, superseded FORTHISPROFILE rather than PASS. Existing morning/
NBAevening automation prompts use thesame default; originalprompts retained and
schedules unchanged. Fullbefore/afterreceipts inAUTOMATIONS.json. Code is isolated
inPR; no mainmerge orproductiondeployment. No source/modelroot, fitting/scoring,
NUTS, weights orTierchange. Rollback reverse scopedconfiguration/promptamendment,
leaving all originalreceipts andforecast/source/model bytes unchanged.
