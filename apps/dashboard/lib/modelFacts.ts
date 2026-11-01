/**
 * Numbers shown on the Model tab. They are copied from the repository docs
 * (docs/ml/backtest-results.md and docs/ml/scale-benchmark.md) and describe
 * SYNTHETIC data and a 2-vCPU test machine; they are not production figures.
 */
export const BACKTEST = {
  wapeBaseline: 0.184,
  wapeModel: 0.126,
  bias: 0.026,
  coverage: 0.809,
  coverageBeforeCalibration: 0.721,
};

export const SCALE: { series: number; features: number; train: number | null; predict: number }[] = [
  { series: 1000, features: 0.2, train: 4.3, predict: 0.03 },
  { series: 5000, features: 1.1, train: 14.6, predict: 0.12 },
  { series: 20000, features: 3.9, train: 78.8, predict: 0.36 },
  { series: 50000, features: 8.6, train: null, predict: 0.82 },
];
