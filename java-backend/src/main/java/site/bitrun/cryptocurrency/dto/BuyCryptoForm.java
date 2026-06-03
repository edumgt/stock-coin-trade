package site.bitrun.cryptocurrency.dto;

import jakarta.validation.constraints.NotEmpty;

public class BuyCryptoForm {

    private String buyMarketCode;

    private String buyType; // 지정가 OR 시장가

    @NotEmpty
    private String buyKrw;

    public BuyCryptoForm(String buyMarketCode, String buyType, String buyKrw) {
        this.buyMarketCode = buyMarketCode;
        this.buyType = buyType;
        this.buyKrw = buyKrw;
    }

    public String getBuyMarketCode() {
        return buyMarketCode;
    }

    public String getBuyType() {
        return buyType;
    }

    public String getBuyKrw() {
        return buyKrw;
    }
}
