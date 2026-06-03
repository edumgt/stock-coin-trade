package site.bitrun.cryptocurrency.global.api.domestic.dto;

import java.util.List;

public class DomesticExchangePriceResponseDto {

    private String marketCode;
    private String symbol;
    private long fetchedAt;
    private List<DomesticExchangePriceItemDto> prices;

    public DomesticExchangePriceResponseDto() {
    }

    public DomesticExchangePriceResponseDto(String marketCode, String symbol, long fetchedAt, List<DomesticExchangePriceItemDto> prices) {
        this.marketCode = marketCode;
        this.symbol = symbol;
        this.fetchedAt = fetchedAt;
        this.prices = prices;
    }

    public String getMarketCode() {
        return marketCode;
    }

    public void setMarketCode(String marketCode) {
        this.marketCode = marketCode;
    }

    public String getSymbol() {
        return symbol;
    }

    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }

    public long getFetchedAt() {
        return fetchedAt;
    }

    public void setFetchedAt(long fetchedAt) {
        this.fetchedAt = fetchedAt;
    }

    public List<DomesticExchangePriceItemDto> getPrices() {
        return prices;
    }

    public void setPrices(List<DomesticExchangePriceItemDto> prices) {
        this.prices = prices;
    }
}
