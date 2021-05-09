library(tidyverse)

lin <- read_lines("config/asins.txt")

dogs <- c("B08HJNKT3P")

categs <- c()
asins <- c()
for (i in seq(lin)) {
  line <- lin[i]
  stsb <-  substr(line, 1, 2)
  if (! stsb %in% c("B0", "\"a")) {
    categ <- line
    next
  } else if (stsb == "\"a") {
    next
  } else if (stsb == "B0") {
    asin <- gsub(line, pattern = "^(B08[A-Z0-9]+) \\- (.+)", replacement = "\\1")
    asins <- c(asins, asin)
    categs <- c(categs, categ)
  }
}

res <- data.frame(categs, asins)
res %<>%
  inner_join(y = countdf, by = c("asins"="asin"))



