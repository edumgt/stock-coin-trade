package site.bitrun.cryptocurrency.global.api.upbit.domain;

import jakarta.persistence.*;

@Entity
public class UpbitMarket {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "upbit_market_id")
    private Long id;

    @Column(name = "market_code")
    private String market;

    private String koreanName;

    private String englishName;

    public UpbitMarket() {
    }

    public UpbitMarket(String market, String koreanName, String englishName) {
        this.market = market;
        this.koreanName = koreanName;
        this.englishName = englishName;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getMarket() {
        return market;
    }

    public void setMarket(String market) {
        this.market = market;
    }

    public String getKoreanName() {
        return koreanName;
    }

    public void setKoreanName(String koreanName) {
        this.koreanName = koreanName;
    }

    public String getEnglishName() {
        return englishName;
    }

    public void setEnglishName(String englishName) {
        this.englishName = englishName;
    }
}
