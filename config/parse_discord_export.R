library(tidyverse)
library(magrittr)

files <- list.files(path = "config/discord_export_may_9", full.names = T)
cats <- gsub(files, pattern = "config/discord_export_may_9/(.+)\\.txt", replacement = "\\1")
names(files) <- cats
dir.create("config/choose_asin/")
dflist <- lapply(seq(files), function(i) {
  cat_now <- names(files)[i]
  file_now <- files[i]
  lines <- read_lines(file_now)
  date_lines <- grep(lines, pattern = "^\\[")
  store <- date_lines + 6
  product_lines1 <- date_lines + 11
  product_lines2 <- date_lines + 10
  df <- data.frame(
    dates = lines[date_lines],
    store1 = lines[store + 1],
    store2 = lines[store],
    products1 = lines[product_lines1],
    products2 = lines[product_lines2],
    products3 = lines[product_lines2 - 1]
  ) %>%
    mutate(
      store = case_when(
        store2 == "Store" ~ store1,
        store1 == "Price" ~ store2,
        TRUE ~ as.character(NA)
      )
    ) %>%
    mutate(
      link = case_when(
        str_detect(products1, pattern = "amazon.com|instockalert.io") ~ products1,
        str_detect(products2, pattern = "amazon.com|instockalert.io") ~ products2,
        str_detect(products3, pattern = "amazon.com|instockalert.io") ~ products3,
        TRUE ~ as.character(NA)
      )
    ) %>%
    filter(! is.na(store) & ! is.na(link) & store == "amazon" ) %>%
    select(dates, store, link) %>%
    mutate(dates = as.Date(tolower(gsub(dates, pattern = "^\\[([a-zA-Z0-9\\-]+) .+\\].+", replacement = "\\1")),
                           format = "%d-%B-%Y")) %>%
    mutate(asin = gsub(link, pattern = ".+/(B08[A-Z0-9]+)[/\\?#].+", replacement = "\\1")) %>%
    mutate(asin = case_when(
      asin == link ~ gsub(link, pattern = ".+/(B08[A-Z0-9]+)", replacement = "\\1"),
      asin != link ~ asin,
      TRUE ~ as.character(NA)
    )) %>%
    filter(str_detect(asin, pattern = ".*http.*", negate = TRUE)) %>%
    mutate(category = cat_now) %>%
    write_csv(paste0("config/choose_asin/", cat_now, ".csv")) %T>%
   {ggplot(data = ., aes(x = dates, fill = asin)) +
    geom_bar(width = 1) +
    facet_wrap(~asin) +
    labs(title = cat_now) +
    ggsave(filename = paste0("config/choose_asin/", cat_now, ".png"), height = 8, width = 8)}
})

final_df <- bind_rows(dflist)
final_df %>%
  group_by(category, asin) %>%
  tally() -> countdf

countdf %>%
  arrange(desc(n)) -> dd

drops <- dd[1:50,]
write_csv(drops, file = "config/drops.csv")

tb <- table(drops$category)



drops <- read_csv("config/drops.csv")
drops

prices <- data.frame(
  category = names(table(drops$category)),
  low = c(300, 300, 400, 550, 1100, 300, 650, 700, 700),
  high = c(600, 800, 950, 1350, 2400, 950, 1100, 1250, 1650)
)

drops %>%
  left_join(prices, by = "category") -> drops_and_price

resl <- lapply(rownames(drops_and_price), function (row) {
  rownow <- drops_and_price[row,]
  list(
    asins = c(rownow$asin),
    "min-price" = rownow$low,
    "max-price" = rownow$high
  )
})

resl2 <- list(
  "items" = resl,
  "amazon_domain" = "smile.amazon.com"
)

jsonlite::write_json(x = resl2, pretty = T, path = "config/amazon_aio_config.json")




