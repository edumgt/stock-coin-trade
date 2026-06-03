package site.bitrun.cryptocurrency.global.api.domestic.dto;

public class DomesticExchangePriceItemDto {

    private String exchangeCode;
    private String exchangeName;
    private Long tradePriceKrw;

    public DomesticExchangePriceItemDto() {
    }

    public DomesticExchangePriceItemDto(String exchangeCode, String exchangeName, Long tradePriceKrw) {
        this.exchangeCode = exchangeCode;
        this.exchangeName = exchangeName;
        this.tradePriceKrw = tradePriceKrw;
    }

    public String getExchangeCode() {
        return exchangeCode;
    }

    public void setExchangeCode(String exchangeCode) {
        this.exchangeCode = exchangeCode;
    }

    public String getExchangeName() {
        return exchangeName;
    }

    public void setExchangeName(String exchangeName) {
        this.exchangeName = exchangeName;
    }

    public Long getTradePriceKrw() {
        return tradePriceKrw;
    }

    public void setTradePriceKrw(Long tradePriceKrw) {
        this.tradePriceKrw = tradePriceKrw;
    }
}
