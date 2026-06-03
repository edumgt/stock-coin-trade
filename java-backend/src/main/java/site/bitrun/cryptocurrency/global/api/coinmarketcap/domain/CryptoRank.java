package site.bitrun.cryptocurrency.global.api.coinmarketcap.domain;

import jakarta.persistence.*;

@Entity
public class CryptoRank {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "crypto_rank_id")
    private Long id;

    private String name;
    private String symbol;
    @Column(name = "api_crypto_id")
    private int apiCryptoId;

    @Embedded
    private InnerQuote quote;

    public CryptoRank() {
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSymbol() {
        return symbol;
    }

    public void setSymbol(String symbol) {
        this.symbol = symbol;
    }

    public InnerQuote getQuote() {
        return quote;
    }

    public void setQuote(InnerQuote quote) {
        this.quote = quote;
    }

    public int getApiCryptoId() {
        return apiCryptoId;
    }

    public void setApiCryptoId(int apiCryptoId) {
        this.apiCryptoId = apiCryptoId;
    }
}

