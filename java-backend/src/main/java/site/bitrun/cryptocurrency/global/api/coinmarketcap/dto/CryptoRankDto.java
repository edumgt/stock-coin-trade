package site.bitrun.cryptocurrency.global.api.coinmarketcap.dto;

import com.fasterxml.jackson.annotation.JsonProperty;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

import java.math.BigDecimal;

public class CryptoRankDto {

    private String name;
    private String symbol;
    @JsonProperty("id")
    private int apiCryptoId;
    private InnerQuote quote;

    public CryptoRankDto() {
    }

    public String getName() {
        return name;
    }

    public String getSymbol() {
        return symbol;
    }

    public int getApiCryptoId() {
        return apiCryptoId;
    }

    public InnerQuote getQuote() {
        return quote;
    }

    public class InnerQuote {
        private InnerUsd usd;

        public InnerQuote() {
        }

        public InnerUsd getUsd() {
            return usd;
        }
        @JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
        public class InnerUsd {
            private float price; // 코인 1개당 가격 - USD
            private BigDecimal marketCap; // 시가 총액 - USD
            @JsonProperty("percent_change_24h")
            private float percentChange24h; // 24시간 변동률
            @JsonProperty("percent_change_7d")
            private float percentChange7d; // 7일간 변동률

            public InnerUsd() {
            }

            public float getPrice() {
                return price;
            }

            public BigDecimal getMarketCap() {
                return marketCap;
            }

            public float getPercentChange24h() {
                return percentChange24h;
            }

            public float getPercentChange7d() {
                return percentChange7d;
            }
        }

    }

}
