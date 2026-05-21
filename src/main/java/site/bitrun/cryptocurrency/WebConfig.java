package site.bitrun.cryptocurrency;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;
import site.bitrun.cryptocurrency.interceptor.LoginCheckInterceptor;

@Configuration
public class WebConfig implements WebMvcConfigurer {

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        registry.addInterceptor(new LoginCheckInterceptor())
                .order(1)
                .addPathPatterns("/**")
                .excludePathPatterns(
                        "/", "/css/**", "/img/**", "/js/**", "/*.ico", "/api/**",
                        "/member/login", "/member/register",
                        "/trade/order", "/trade/stock"
                );
    }
}
