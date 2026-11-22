import os
import sys

# Make docker/broker/librevdi_ext importable without the broker image
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docker", "broker"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "docker", "broker", "branding"))
