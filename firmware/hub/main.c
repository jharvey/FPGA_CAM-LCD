/* Sensor-hub entry point on the LiteX soft CPU.  DRAFT, not built. */
#include "../common/app.h"
#include "../common/board.h"
#include <generated/csr.h>
#include <irq.h>

void hub_timer_isr(void);

static app_t app;

void isr(void)                                   /* LiteX calls this for every interrupt */
{
    if (irq_pending() & (1 << TIMER0_INTERRUPT))
        hub_timer_isr();
}

int main(void)
{
    /* timer0: 1 kHz periodic */
    timer0_en_write(0);
    timer0_reload_write(CONFIG_CLOCK_FREQUENCY / 1000);
    timer0_load_write(CONFIG_CLOCK_FREQUENCY / 1000);
    timer0_en_write(1);
    timer0_ev_enable_write(1);
    irq_setmask(irq_getmask() | (1 << TIMER0_INTERRUPT));
    irq_setie(1);

    app_init(&app);
    uint32_t next = hal_millis();
    for (;;)
    {
        while ((int32_t)(hal_millis() - next) < 0) {}
        next += 1000 / HUB_RATE_HZ;
        app_tick(&app);
    }
}
