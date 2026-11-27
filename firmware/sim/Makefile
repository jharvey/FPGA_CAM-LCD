# Host build of the sensor-hub code + simulator.   make && ./fcl_sim out.csv && python3 plot.py out.csv
CC ?= gcc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wno-unused-parameter -D_DEFAULT_SOURCE
COMMON = ../common/app.c ../common/sensors.c ../common/fusion.c ../common/link.c ../common/osd.c
SRC = sim.c $(COMMON)

fcl_sim: $(SRC) ../common/*.h
	$(CC) $(CFLAGS) -o $@ $(SRC) -lm

# live back end for fcl_sim.py (real hub code behind the simulated USB port)
fcl_sim_live: sim_live.c sim.c $(COMMON) ../common/*.h
	$(CC) $(CFLAGS) -o $@ sim_live.c $(COMMON) -lm

all: fcl_sim fcl_sim_live

test: fcl_sim
	./fcl_sim fcl_sim.csv

clean:
	rm -f fcl_sim fcl_sim_live fcl_sim.csv fcl_sim.png
.PHONY: test clean
