"""One shared empirical log-environment draw per game, not per player."""
import numpy as np


def sample_state(parameters, rng, *, kind='G1'):
    if kind not in ('G0','G1'):raise ValueError('UNKNOWN_GAME_STATE')
    if kind=='G0':
        overtime=0; latent=np.zeros(3)
    else:
        overtime=int(rng.geometric(1-parameters['ot_continuation'])) if rng.random()<parameters['ot_probability'] else 0
        cov=np.asarray(parameters['log_cov'],dtype=float)
        if cov.shape!=(3,3) or not np.all(np.isfinite(cov)) or np.linalg.eigvalsh(cov).min() < -1e-10:
            raise ValueError('INVALID_STATE_COVARIANCE')
        latent=rng.multivariate_normal(-np.diag(cov)/2,cov)
    duration=48.+5*overtime
    pace=parameters['pace_mean']*np.exp(latent[0])
    return {'overtime':overtime,'duration':duration,'regulation_possession_proxy':float(pace),
            'team_possession_proxy':np.repeat(pace*duration/48,2).tolist(),
            'offensive_effect':np.exp(latent[1:]).tolist(), 'latent':latent.tolist(),
            'proxy_definition':'FGA + 0.44 FTA - OREB + TOV, two-team mean; box-score estimate, not observed possessions',
            'state_kind':kind}
