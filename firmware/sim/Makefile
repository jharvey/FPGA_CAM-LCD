# Host build of the sensor-hub code + simulator.   make && ./fcl_sim out.csv && python3 plot.py out.csv
CC ?= gcc
CFLAGS ?= -O2 -std=c11 -Wall -Wextra -Wno-unused-parameter -D_DEFAULT_SOURCE
SRC = sim.c ../common/app.c ../common/sensors.c ../common/fusion.c ../common/link.c

fcl_sim: $(SRC) ../common/*.h
	$(CC) $(CFLAGS) -o $@ $(SRC) -lm

test: fcl_sim
	./fcl_sim fcl_sim.csv

clean:
	rm -f fcl_sim fcl_sim.csv fcl_sim.png
.PHONY: test clean
