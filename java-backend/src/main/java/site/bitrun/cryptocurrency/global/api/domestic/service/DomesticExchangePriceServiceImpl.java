package site.bitrun.cryptocurrency.global.api.domestic.service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;
import site.bitrun.cryptocurrency.global.api.domestic.dto.DomesticExchangePriceItemDto;
import site.bitrun.cryptocurrency.global.api.domestic.dto.DomesticExchangePriceResponseDto;

import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Locale;

@Slf4j
@Service
public class DomesticExchangePriceServiceImpl implements DomesticExchangePriceService {

    private final RestTemplate restTemplate;
    private final ObjectMapper objectMapper;

    public DomesticExchangePriceServiceImpl(RestTemplateBuilder restTemplateBuilder, ObjectMapper objectMapper) {
        this.restTemplate = restTemplateBuilder
                .setConnectTimeout(Duration.ofSeconds(2))
                .setReadTimeout(Duration.ofSeconds(2))
                .build();
        this.objectMapper = objectMapper;
    }

    @Override
    public DomesticExchangePriceResponseDto getDomesticPrices(String marketCode) {
        String symbol = extractSymbol(marketCode);
        String normalizedMarketCode = "KRW-" + symbol;

        List<DomesticExchangePriceItemDto> prices = new ArrayList<>();
        prices.add(new DomesticExchangePriceItemDto("UPBIT", "업비트", fetchUpbitPrice(normalizedMarketCode)));
        prices.add(new DomesticExchangePriceItemDto("BITHUMB", "빗썸", fetchBithumbPrice(symbol)));
        prices.add(new DomesticExchangePriceItemDto("COINONE", "코인원", fetchCoinonePrice(symbol)));
        prices.add(new DomesticExchangePriceItemDto("KORBIT", "코빗", fetchKorbitPrice(symbol)));

        return new DomesticExchangePriceResponseDto(normalizedMarketCode, symbol, System.currentTimeMillis(), prices);
    }

    private String extractSymbol(String marketCode) {
        if (marketCode == null || marketCode.isBlank()) {
            return "BTC";
        }

        String normalized = marketCode.trim().toUpperCase(Locale.ROOT);
        String[] split = normalized.split("-");
        if (split.length == 2 && !split[1].isBlank()) {
            return split[1];
        }
        return normalized;
    }

    private Long fetchUpbitPrice(String marketCode) {
        String url = "https://api.upbit.com/v1/ticker?markets=" + marketCode;
        return fetchPriceSafely("UPBIT", url, root -> {
            if (!root.isArray() || root.isEmpty()) {
                return null;
            }
            return toLongPrice(root.get(0).path("trade_price"));
        });
    }

    private Long fetchBithumbPrice(String symbol) {
        String url = "https://api.bithumb.com/public/ticker/" + symbol + "_KRW";
        return fetchPriceSafely("BITHUMB", url, root -> toLongPrice(root.path("data").path("closing_price")));
    }

    private Long fetchCoinonePrice(String symbol) {
        String url = "https://api.coinone.co.kr/public/v2/ticker_new/KRW/" + symbol;
        return fetchPriceSafely("COINONE", url, root -> {
            JsonNode tickers = root.path("tickers");
            if (!tickers.isArray() || tickers.isEmpty()) {
                return null;
            }
            return toLongPrice(tickers.get(0).path("last"));
        });
    }

    private Long fetchKorbitPrice(String symbol) {
        String url = "https://api.korbit.co.kr/v1/ticker/detailed?currency_pair="
                + symbol.toLowerCase(Locale.ROOT) + "_krw";
        return fetchPriceSafely("KORBIT", url, root -> toLongPrice(root.path("last")));
    }

    private Long fetchPriceSafely(String exchangeCode, String url, JsonPriceExtractor extractor) {
        try {
            String response = restTemplate.getForObject(url, String.class);
            if (response == null || response.isBlank()) {
                return null;
            }

            JsonNode root = objectMapper.readTree(response);
            return extractor.extract(root);
        } catch (Exception ex) {
            log.debug("{} price fetch failed: {}", exchangeCode, ex.getMessage());
            return null;
        }
    }

    private Long toLongPrice(JsonNode node) {
        if (node == null || node.isMissingNode() || node.isNull()) {
            return null;
        }

        if (node.isNumber()) {
            return Math.round(node.asDouble());
        }

        if (node.isTextual()) {
            String value = node.asText().trim();
            if (value.isEmpty()) {
                return null;
            }
            try {
                return Math.round(Double.parseDouble(value));
            } catch (NumberFormatException ignored) {
                return null;
            }
        }

        return null;
    }

    @FunctionalInterface
    private interface JsonPriceExtractor {
        Long extract(JsonNode root);
    }
}
