package site.bitrun.cryptocurrency.dto;

public class HoldCryptoDto {

    private String marketCode;
    private String marketCodeOnlySymbol;
    private String koreanName;
    private double holdCount;
    private double buyAverage;
    private double buyTotalKrw;

    public HoldCryptoDto(String marketCode, String marketCodeOnlySymbol, String koreanName, double holdCount, double buyAverage, double buyTotalKrw) {
        this.marketCode = marketCode;
        this.marketCodeOnlySymbol = marketCodeOnlySymbol;
        this.koreanName = koreanName;
        this.holdCount = holdCount;
        this.buyAverage = buyAverage;
        this.buyTotalKrw = buyTotalKrw;
    }

    public String getMarketCode() {
        return marketCode;
    }

    public void setMarketCode(String marketCode) {
        this.marketCode = marketCode;
    }

    public String getMarketCodeOnlySymbol() {
        return marketCodeOnlySymbol;
    }

    public void setMarketCodeOnlySymbol(String marketCodeOnlySymbol) {
        this.marketCodeOnlySymbol = marketCodeOnlySymbol;
    }

    public String getKoreanName() {
        return koreanName;
    }

    public void setKoreanName(String koreanName) {
        this.koreanName = koreanName;
    }

    public double getHoldCount() {
        return holdCount;
    }

    public void setHoldCount(double holdCount) {
        this.holdCount = holdCount;
    }

    public double getBuyAverage() {
        return buyAverage;
    }

    public void setBuyAverage(double buyAverage) {
        this.buyAverage = buyAverage;
    }

    public double getBuyTotalKrw() {
        return buyTotalKrw;
    }

    public void setBuyTotalKrw(double buyTotalKrw) {
        this.buyTotalKrw = buyTotalKrw;
    }
}
