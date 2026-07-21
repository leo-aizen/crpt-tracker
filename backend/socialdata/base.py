"""Social adapter contract.

activity(symbols) returns, per OUR canonical ticker that the provider covers:
  {symbol: {
      "watchers": int|None,          # people following the symbol
      "post_rate_per_day": float|None,  # estimated from the latest sample
      "sample_size": int,            # posts the estimate is based on
      "posts": [ {"id", "body", "user", "likes", "created_utc", "url"} ... ]
  }}
Symbols the provider doesn't cover are ABSENT — the UI renders "no data",
never a zero that looks like measured silence.
"""


class SocialAdapter:
    name = "base"
    source_label = "no social provider configured"

    def activity(self, symbols):
        raise NotImplementedError
