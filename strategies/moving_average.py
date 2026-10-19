from engine.strategy import Strategy, register_strategy


@register_strategy
class MovingAverageStrategy(Strategy):
  strategy_id = "moving_average"
  version = "1.0"
  name = "Moving average"
  description = "Compares fast and slow close-price moving averages."
  default_parameters = {"fast_window": 3, "slow_window": 5}

  def __init__(
    self,
    fast_window=3,
    slow_window=5
  ):
    super().__init__(fast_window=fast_window, slow_window=slow_window)
    self.fast_window = self.parameters["fast_window"]
    self.slow_window = self.parameters["slow_window"]

  @classmethod
  def validate_parameters(cls, parameters):
    fast, slow = parameters["fast_window"], parameters["slow_window"]
    if isinstance(fast, bool) or not isinstance(fast, int) or fast < 1:
      raise ValueError("fast_window must be a positive integer.")
    if isinstance(slow, bool) or not isinstance(slow, int) or slow < 2:
      raise ValueError("slow_window must be an integer of at least 2.")
    if fast >= slow:
      raise ValueError("fast_window must be smaller than slow_window.")

  @property
  def required_lookback(self):
    return self.slow_window

  def generate_signal(self, data):

    data = data.copy()

    data["fast_ma"] = (
      data["Close"]
      .rolling(window=self.fast_window)
      .mean()
    )

    data["slow_ma"] = (
      data["Close"]
      .rolling(window=self.slow_window)
      .mean()
    )

    data["signal"] = "HOLD"
    data["signal_strength"] = 0.0

    for i in range(len(data)):

      fast_ma = data.iloc[i]["fast_ma"]
      slow_ma = data.iloc[i]["slow_ma"]

      if (
        fast_ma != fast_ma
        or slow_ma != slow_ma
        or slow_ma == 0
      ):
        continue

      strength = abs(
        fast_ma - slow_ma
      ) / slow_ma

      lookback = 20

      start = max(
        0,
        i - lookback
      )

      historical_strengths = []

      for j in range(start, i):
        previous_fast_ma = data.iloc[j]["fast_ma"]
        previous_slow_ma = data.iloc[j]["slow_ma"]

        if (
          previous_fast_ma != previous_fast_ma
          or previous_slow_ma != previous_slow_ma
          or previous_slow_ma == 0
        ):
          continue

        previous_strength = abs(
          previous_fast_ma - previous_slow_ma
        ) / previous_slow_ma

        historical_strengths.append(
          previous_strength
        )

      if len(historical_strengths) >= 5:

        historical_strengths.sort()

        rank = 0

        for previous_strength in historical_strengths:

          if previous_strength <= strength:
            rank += 1

        confidence = (
          rank / len(historical_strengths)
        )

      else:
        confidence = 0.5

      data.loc[
        data.index[i],
        "signal_strength"
      ] = confidence

      if fast_ma > slow_ma:
        data.loc[
          data.index[i],
          "signal"
        ] = "BUY"

      elif fast_ma < slow_ma:
        data.loc[
          data.index[i],
          "signal"
        ] = "SELL"

    return data
