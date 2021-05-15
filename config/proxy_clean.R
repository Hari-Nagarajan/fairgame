library(tidyverse)

proxies <- read_table("config/proxies.txt", col_names = c("Proxies"))
prox <- proxies %>%
  mutate(Proxies = paste0("OR1449719690:7a30g6pv@", Proxies))
splitprox <- split(prox$Proxies, rep(seq(20), each = 5))

dir.create("config/proxies", showWarnings = F)
lapply(seq(splitprox), function(i) {
  proxnowlist <- splitprox[[i]]
  list(
    'proxies' = lapply(proxnowlist, function (proxnow) {
        list(
          "http" = paste0("http://", proxnow),
          "https" = paste0("https://", proxnow)
        )
      })
  ) %>%
    jsonlite::write_json(path = paste0("config/proxies/proxies.", i, ".json"), auto_unbox = T, pretty = T)
})
