package site.bitrun.cryptocurrency.global.api.coinmarketcap.domain;

import jakarta.persistence.Embeddable;
import jakarta.persistence.Embedded;

@Embeddable
public class InnerQuote {
    @Embedded
    private InnerUsd usd;

    public InnerUsd getUsd() {
        return usd;
    }

    public void setUsd(InnerUsd usd) {
        this.usd = usd;
    }
}
