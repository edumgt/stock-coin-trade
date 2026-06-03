package site.bitrun.cryptocurrency.domain;

import jakarta.persistence.*;
import site.bitrun.cryptocurrency.global.api.upbit.domain.UpbitMarket;

@Entity
public class HoldCrypto {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    @Column(name = "hold_crypto_id")
    private Long id;

    @ManyToOne
    @JoinColumn(name = "member_id")
    private Member member;

    @ManyToOne
    @JoinColumn(name = "upbit_market_id")
    private UpbitMarket upbitMarket;

    private double buyCryptoCount; // 보유 코인 수량
    private double buyAverage; // 평단가
    private long buyTotalKrw; // 총 매수 금액(KRW)

    public HoldCrypto() {
    }

    public HoldCrypto(Member member, UpbitMarket upbitMarket, double buyCryptoCount, double buyAverage, long buyTotalKrw) {
        this.member = member;
        this.upbitMarket = upbitMarket;
        this.buyCryptoCount = buyCryptoCount;
        this.buyAverage = buyAverage;
        this.buyTotalKrw = buyTotalKrw;
    }

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Member getMember() {
        return member;
    }

    public void setMember(Member member) {
        this.member = member;
    }

    public UpbitMarket getUpbitMarket() {
        return upbitMarket;
    }

    public void setUpbitMarket(UpbitMarket upbitMarket) {
        this.upbitMarket = upbitMarket;
    }

    public double getBuyCryptoCount() {
        return buyCryptoCount;
    }

    public void setBuyCryptoCount(double buyCryptoCount) {
        this.buyCryptoCount = buyCryptoCount;
    }

    public double getBuyAverage() {
        return buyAverage;
    }

    public void setBuyAverage(double buyAverage) {
        this.buyAverage = buyAverage;
    }

    public long getBuyTotalKrw() {
        return buyTotalKrw;
    }

    public void setBuyTotalKrw(long buyTotalKrw) {
        this.buyTotalKrw = buyTotalKrw;
    }

}
