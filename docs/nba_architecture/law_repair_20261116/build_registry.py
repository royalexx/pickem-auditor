"""Append current invariants without rewriting the rejected candidate's registry."""
import ast,json,pathlib
root=pathlib.Path.cwd();out=root/'docs/nba_architecture/law_repair_20261116'
r=json.loads((root/'docs/nba_architecture/completion_20261116/invariants.json').read_text())
r.update(registry_version='1.2.0',rejected_parent='e1983b2d0b94742dfb1bf411694dc46c7cad1ac6',unresolved_g0=[])
f='tests/nba_architecture/test_g0_law_repair_20261116.py::'
def entry(id,requirement,validators,negative,positive):
 return dict(id=id,requirement=requirement,objects_and_fields=['pregame.players legal exclusion','G OT scenario weights','O players participation probability and conditional support/mass','positive-weight O sampled states','S_O/S_O_J conditioning and PMF'],producer='P3 O; P4 G/J; P2 S; P5 C integration',validators=validators,gate='G0',dependencies=['MINUTES_LAW','MINUTE_CONSERVATION','EXACT_G_O_J','CONDITIONING'],rejection='ContractError; budget/solver/residual failure is uncertified, never accepted',negative_tests=[f+x for x in negative],positive_tests=[f+x for x in positive],resealing='All mutations reseal O/J/distribution/original offer and downstream view as applicable',audit_status='AUTHOR_REPAIRED_PENDING_SEPARATE_INDEPENDENT_REVIEW')
r['invariants'] += [
 entry('CONSERVING_LAW_COUPLING','There must exist a nonnegative joint measure on conserving team allocations. G-state sums equal normalized declared G probabilities; every played-state marginal is q_i*f_i and every DNP marginal is 1-q_i. Unknown q_i is existentially bounded [0,1]. Every positive-weight observed joint state must have positive probability under some compatible coupling; convex mixtures preserve all finite observed supports. Never equate empirical frequencies to declared law masses.',['validate_opportunity','validate_exposure_coupling','_check_team'],['test_f1_unattainable_minute_atom_rejected_at_all_boundaries','test_marginal_masses_incompatible_even_when_each_atom_attainable','test_overtime_probability_and_marginals_are_jointly_bound','test_observed_label_must_have_positive_compatible_probability'],['test_feasible_exchange_without_empirical_frequency_equality','test_exact_two_player_exchange_grid','test_fractional_minutes_and_permutation','test_empirical_joint_frequency_need_not_equal_law_mass']),
 entry('EXPOSURE_COUNT_DOMINANCE','For any full forecast, zero possible exposure requires P(count>0)=0 exactly. Analytic unconditional/declared-roster laws require P(count>0)<=sup P(M>0), with the supremum taken over compatible joint exposure laws. Add the analytic count constraint back to the coupling so it preserves positive observed-state support. Participation-conditional analytic bounds use f_i(M>0), and the conditioning event must be possible. Interior empirical MC frequencies are not constrained to equal or lie below theoretical probabilities.',['validate_forecast','validate_settlement','positive_exposure_bound','validate_exposure_coupling'],['test_f2_all_eight_markets_zero_exposure_rejected_at_forecast_and_c','test_nonzero_count_mass_cannot_exceed_positive_exposure_mass','test_positive_counterfactual_support_can_be_forced_out_by_team_pool','test_count_certainty_cannot_force_observed_dnp_to_probability_zero','test_zero_exposure_rejects_even_tiny_positive_mass'],['test_f2_zero_count_positive_counterparts_all_markets','test_conditional_minutes_do_not_invent_certain_participation','test_empirical_s_o_interior_frequency_is_not_a_hard_endpoint','test_participation_conditioning_uses_conditional_exposure_bound']),
 entry('COUPLING_CERTIFICATION','Normalize only within already validated mass tolerances. Enumeration minute residual <=1e-7; LP primal equalities/bounds residual <=1e-12. Positive G states and unattainable positive atoms are checked structurally regardless of small mass. An unattainable conditional atom forces unknown q=0 using a unit-scale row. Numerical underflow, solver failure, or verification budget exhaustion fails closed as uncertified.',['_check_team'],['test_positive_atom_cannot_be_hidden_below_solver_tolerance','test_tiny_positive_overtime_state_cannot_be_dropped','test_unattainable_tiny_atom_forces_unknown_participation_to_zero','test_verification_budget_fails_closed'],['test_exact_two_player_exchange_grid','test_fractional_minutes_and_permutation'])]
(out/'invariants.json').write_text(json.dumps(r,indent=2)+'\n')
checks=[]
class Inventory(ast.NodeVisitor):
 def __init__(self,file):self.file=file;self.stack=[]
 def visit_FunctionDef(self,node):
  self.stack.append(node.name);self.generic_visit(node);self.stack.pop()
 def visit_Call(self,node):
  if isinstance(node.func,ast.Name) and node.func.id=='req':
   checks.append(dict(file=self.file,validator='.'.join(self.stack),line=node.lineno,requirement=ast.unparse(node.args[0]),code=ast.unparse(node.args[1]),registry_groups=['CONSERVING_LAW_COUPLING','EXPOSURE_COUNT_DOMINANCE','COUPLING_CERTIFICATION']))
  self.generic_visit(node)
for p in ['v2/nba_architecture/exposure_v2.py','v2/nba_architecture/families_v2.py']:
 Inventory(p).visit(ast.parse((root/p).read_text()))
(out/'check_inventory.json').write_text(json.dumps(dict(parent_inventory='docs/nba_architecture/completion_20261116/check_inventory.json',current_checks=checks),indent=2)+'\n')
methods={}
for p in (root/'tests/nba_architecture').glob('test_*.py'):
 for node in ast.walk(ast.parse(p.read_text())):
  if isinstance(node,ast.FunctionDef) and node.name.startswith('test_'):methods[node.name]=str(p.relative_to(root))+'::'+node.name
(out/'test_inventory.json').write_text(json.dumps(methods,indent=2)+'\n')
for e in r['invariants']:
 for ref in e['negative_tests']+e['positive_tests']:
  file,name=ref.split('::');assert any(isinstance(n,ast.FunctionDef) and n.name==name for n in ast.walk(ast.parse((root/file).read_text()))),ref
print(len(r['invariants']),'invariant groups, all test references resolved')
