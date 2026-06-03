package site.bitrun.cryptocurrency.global.api.coinmarketcap.domain;

import jakarta.persistence.Embeddable;

import java.math.BigDecimal;

@Embeddable
public class InnerUsd {

    private float price;
    private BigDecimal marketCap;
    private float percentChange24h; // 24시간 변동률
    private float percentChange7d; // 7일간 변동률

    public float getPrice() {
        return price;
    }

    public void setPrice(float price) {
        this.price = price;
    }

    public BigDecimal getMarketCap() {
        return marketCap;
    }

    public void setMarketCap(BigDecimal marketCap) {
        this.marketCap = marketCap;
    }

    public float getPercentChange24h() {
        return percentChange24h;
    }

    public void setPercentChange24h(float percentChange24h) {
        this.percentChange24h = percentChange24h;
    }

    public float getPercentChange7d() {
        return percentChange7d;
    }

    public void setPercentChange7d(float percentChange7d) {
        this.percentChange7d = percentChange7d;
    }
}
