package site.bitrun.cryptocurrency.global.api.upbit.dto;

import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.annotation.JsonNaming;

// 업비트 API 현재가 json과 매핑할 클래스
@JsonNaming(PropertyNamingStrategies.SnakeCaseStrategy.class)
public class UpbitTradePriceDto {
    private String tradePrice;

    public UpbitTradePriceDto() {
    }

    public UpbitTradePriceDto(String tradePrice) {
        this.tradePrice = tradePrice;
    }

    public String getTradePrice() {
        return tradePrice;
    }

    public void setTradePrice(String tradePrice) {
        this.tradePrice = tradePrice;
    }
}