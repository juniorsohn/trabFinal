

# Compilador e flags
CC       := mpicc
CFLAGS   := -O2
TARGET   := main
SRCS     := main.c

# Número de processos padrão para o run
NP       := 4

.PHONY: all clean run

all: $(TARGET)

$(TARGET): $(SRCS)
	$(CC) $(CFLAGS) -o $@ $^

run: $(TARGET)
	mpirun -np $(NP) ./$(TARGET)

clean:
	rm -f $(TARGET)

