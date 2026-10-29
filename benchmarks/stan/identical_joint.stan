// Same hierarchical likelihood/priors as scripts/joint_population_bayes.py.
// Single/multi-season, NB count or Student-t signed yards. Research only.
data {
 int<lower=1> N; int<lower=1> P; int<lower=1> G;
 int<lower=1> S; int<lower=1> O;
 int<lower=0,upper=1> season_on; int<lower=0,upper=1> is_count;
 array[N] int<lower=1,upper=P> p;
 array[N] int<lower=1,upper=G> group;
 array[N] int<lower=1,upper=S> season;
 array[N] int<lower=1,upper=O> opponent;
 array[N] int<lower=0,upper=1> home;
 vector<lower=0>[N] workload;
 vector[N] log_workload; vector[N] y_value;
 array[N] int<lower=0> y_count;
 real base_work; real rate_prior_mean; real<lower=0> rate_prior_sd;
 real<lower=0> opponent_prior_sd; real<lower=0> home_prior_sd;
 real<lower=0> season_rate_prior_sd;
}
parameters {
 vector[G] population_workload;
 vector[G] population_rate;
 vector<lower=0>[2] player_sd;
 cholesky_factor_corr[2] player_L_corr;
 matrix[2,P] player_z;
 vector<lower=0>[season_on] season_workload_sd;
 vector<lower=0>[season_on] season_rate_sd;
 matrix[season_on,S] season_workload_z;
 matrix[season_on,S] season_rate_z;
 real<lower=0> opponent_rate_sd;
 vector[O] opponent_rate_z;
 real home_effect;
 real<lower=0> workload_sigma;
 vector<lower=0>[is_count] count_dispersion_array;
 vector<lower=0>[1-is_count] yardage_sigma_array;
}
transformed parameters {
 matrix[P,2] player_effect=(diag_pre_multiply(player_sd,player_L_corr)*player_z)';
 vector[O] opponent_rate=(opponent_rate_z-mean(opponent_rate_z))*opponent_rate_sd;
 vector[S] season_workload=rep_vector(0,S);
 vector[S] season_rate=rep_vector(0,S);
 if (season_on==1) {
   season_workload=((season_workload_z[1])'-rep_vector(mean(season_workload_z[1]),S))*season_workload_sd[1];
   season_rate=((season_rate_z[1])'-rep_vector(mean(season_rate_z[1]),S))*season_rate_sd[1];
 }
}
model {
 population_workload ~ normal(base_work,1);
 population_rate ~ normal(rate_prior_mean,rate_prior_sd);
 player_sd ~ normal(0,0.6);
 player_L_corr ~ lkj_corr_cholesky(2);
 to_vector(player_z) ~ normal(0,1);
 season_workload_sd ~ normal(0,0.2);
 season_rate_sd ~ normal(0,season_rate_prior_sd);
 to_vector(season_workload_z) ~ normal(0,1);
 to_vector(season_rate_z) ~ normal(0,1);
 opponent_rate_sd ~ normal(0,opponent_prior_sd);
 opponent_rate_z ~ normal(0,1);
 home_effect ~ normal(0,home_prior_sd);
 workload_sigma ~ normal(0,0.45);
 if (is_count==1) count_dispersion_array[1] ~ gamma(3,0.35);
 else yardage_sigma_array[1] ~ normal(0,60);
 for(i in 1:N) {
   real rate=population_rate[group[i]]+player_effect[p[i],2]
      +season_rate[season[i]]+opponent_rate[opponent[i]]+home[i]*home_effect;
   log_workload[i] ~ normal(population_workload[group[i]]
      +player_effect[p[i],1]+season_workload[season[i]],workload_sigma);
   if(is_count==1)
     y_count[i] ~ neg_binomial_2(workload[i]*exp(rate),count_dispersion_array[1]);
   else
     y_value[i] ~ student_t(4,workload[i]*rate,yardage_sigma_array[1]);
 }
}
generated quantities {
 real count_dispersion=0;
 real yardage_sigma=0;
 if(is_count==1) count_dispersion=count_dispersion_array[1];
 else yardage_sigma=yardage_sigma_array[1];
}
