import datetime
import struct
from typing import Tuple
import logging
import struct


logger = logging.getLogger("pygmc.device")


class SimpleDevice:
    def __init__(self, con):
        """
        A GMC device. Can be used with:
        GMC-300, GMC-320, GMC-500, GMC-500+, GMC-600, GMC-600+

        Parameters
        ----------
        con : pygmc.Connection
            An connection interface to the USB device.
        """
        # TODO: Refactor to "connection"
        logger.debug("Initialize SimpleDevice")
        self.con = con

    def get_version(self) -> str:
        """
        Get version of device.
        Has a sleep wait to read as spec RFC1801 doesn't specify
        end char nor byte size.

        Returns
        -------
        str
            Device version
        """
        cmd = b"<GETVER>>"
        result = self.con.get(cmd)
        return result.decode("utf8")

    def get_serial(self) -> str:
        cmd = b"<GETSERIAL>>"
        result = self.con.get_exact(cmd, size=7)
        return result.hex()

    def get_voltage(self) -> float:
        """
        Get device voltage

        Returns
        -------
        float
            Device voltage in volts

        Notes
        -----
        Device only has resolution to tenth of a volt despite example in spec RFC1801.

        """
        # Device only has resolution to tenth of a volt despite example in spec RFC1801.
        cmd = b"<GETVOLT>>"
        result = self.con.get_exact(cmd, size=5)
        # result example: b'4.8v\x00'
        result = float(result[0:3])  # e.g. float(b'4.8')
        return result

    def get_cpm(self) -> int:
        """
        Get CPM counts-per-minute data
        Specs don't provide how CPM is computed nor if both high/low tubes are used.

        Returns
        -------
        int
            Counts per minute (GMC has 2 tubes, assumed cpm accounts for both?)
        """
        # A 32 bit unsigned integer is returned. In total 4 bytes data return from GQ GMC unit. The first byte is MSB byte data and fourth byte is LSB byte data.
        # e.g.: 00 00 00 1C     the returned CPM is 28. big-endian
        cmd = b"<GETCPM>>"
        result = self.con.get_exact(cmd, size=4)
        count = struct.unpack(">I", result)[0]
        return count

    def get_datetime(self) -> datetime.datetime:
        """
        Get device datetime

        Returns
        -------
        datetime.datetime
            Device datetime
        """
        # Return: Seven bytes data: YY MM DD HH MM SS 0xAA
        cmd = b"<GETDATETIME>>"
        data = self.con.get_exact(cmd, size=7)
        year = int("20{0:2d}".format(data[0]))
        month = int("{0:2d}".format(data[1]))
        day = int("{0:2d}".format(data[2]))
        hour = int("{0:2d}".format(data[3]))
        minute = int("{0:2d}".format(data[4]))
        second = int("{0:2d}".format(data[5]))
        return datetime.datetime(year, month, day, hour, minute, second)


class Device(SimpleDevice):
    def __init__(self, con):
        """
        A GMC device. Can be used with:
        GMC-300, GMC-320, GMC-500, GMC-500+, GMC-600, GMC-600+

        Parameters
        ----------
        con : pygmc.Connection
            An connection interface to the USB device.
        """
        super().__init__(con)

    def get_gyro(self) -> Tuple[int, int, int]:
        """
        Get gyroscope data. No units specified in spec RFC1801 nor RFC1201 :(

        Returns
        -------
        Tuple[int, int, int]
            (X, Y, Z) gyroscope data
        """
        cmd = b"<GETGYRO>>"
        # Return: Seven bytes gyroscope data in hexdecimal: BYTE1,BYTE2,BYTE3,BYTE4,BYTE5,BYTE6,BYTE7
        # Here: BYTE1,BYTE2 are the X position data in 16 bits value. The first byte is MSB byte data and second byte is LSB byte data.
        # BYTE3,BYTE4 are the Y position data in 16 bits value. The first byte is MSB byte data and second byte is LSB byte data.
        # BYTE5,BYTE6 are the Z position data in 16 bits value. The first byte is MSB byte data and second byte is LSB byte data.
        # BYTE7 always 0xAA
        result = self.con.get_exact(cmd, size=7)
        x, y, z, dummy = struct.unpack(">hhhB", result)
        return x, y, z

    def get_cps(self) -> int:
        """
        Get CPS counts-per-second
        Specs don't provide how CPS is computed

        Returns
        -------
        int
            Counts per second
        """
        cmd = b"<GETCPS>>"
        result = self.con.get_exact(cmd, size=4)
        count = struct.unpack(">I", result)[0]
        return count

    def get_cpmh(self) -> int:
        """
        Get CPM of the high dose tube
        Only GMC-500+ supported (spec RFC1801)

        Returns
        -------
        int
            Counts per minute on high dose tube (GMC has 2 tubes)
        """
        #
        # A 32 bit unsigned integer is returned. In total 4 bytes data return from GQ GMC unit. The first byte is MSB byte data and fourth byte is LSB byte data.
        # e.g.: 00 00 00 1C     the returned CPM is 28. big-endian
        cmd = b"<GETCPMH>>"
        result = self.con.get_exact(cmd, size=4)
        count = struct.unpack(">I", result)[0]
        return count

    def get_cpml(self) -> int:
        """
        Get CPM of the low dose tube
        Only GMC-500+ supported (spec RFC1801)

        Returns
        -------
        int
             Counts per minute on low dose tube (GMC has 2 tubes)
        """
        cmd = b"<GETCPML>>"
        result = self.con.get_exact(cmd, size=4)
        count = struct.unpack(">I", result)[0]
        return count

    def heartbeat_on(self) -> None:
        """
        Turn heartbeat ON.
        CPS data is automatically written to the buffer every second.
        """
        self.con.write(b"<HEARTBEAT1>>")
        logger.debug("Heartbeat ON")

    def heartbeat_off(self) -> None:
        """
        Turn heartbeat OFF.
        Stop writing data to buffer every second.
        """
        self.con.write(b"<HEARTBEAT0>>")
        logger.debug("Heartbeat OFF")

    def heartbeat_live(self, count=60, byte_size=4) -> int:
        """
        Get live CPS data, as a generator. i.e. yield (return) CPS as available.

        Parameters
        ----------
        count : int, optional
            How many CPS counts to return (default=60). Theoretically, 1 count = 1 second.
            Wall-clock time can be a bit higher or lower.
        byte_size : int, optional
            Expected result size, by default 4.
            GMC-500=4, GMC-320=2

        Returns
        -------
        int
            CPS - Counts-Per-Second

        Yields
        ------
        Iterator[int]
            CPS
        """
        self.con.reset_buffers()
        for i in range(count):
            raw = self.con.read_until(size=byte_size)
            cps = struct.unpack(">I", raw)[0]
            yield cps

    def heartbeat_live_print(self, count=60, byte_size=4) -> None:
        """
        Print live CPS data.

        Parameters
        ----------
        count : int, optional
            How many CPS counts to return (default=60). Theoretically, 1 count = 1 second.
            Wall-clock time can be a bit higher or lower.
        byte_size : int, optional
            Expected result size, by default 4.
            GMC-500=4, GMC-320=2

        """
        max_ = 0
        i = 0
        self.con.reset_buffers()
        for cps in self.heartbeat_live(count=count, byte_size=byte_size):
            i += 1
            if cps > max_:
                max_ = cps
            # empty leading space for terminal cursor
            msg = f" cps={cps:<2} | max={max_:<2} | loop={i:<10,}"
            print(msg, end="\r")  # Carriage return - update line we just printed

    # To-be-added soon(TM)
    # def _history(self, start_position, size):
    #     # <SPIR[A2][A1][A0][L1][L0]>>
    #     # A2,A1,A0 are three bytes address data, from MSB to LSB.
    #     # The L1,L0 are the data length requested.  L1 is high byte of 16 bit integer and L0 is low byte.
    #     # \xff is end of file?
    #     start = struct.pack(">I", start_position)[1:]
    #     # 2**11 = 2048
    #     size = struct.pack(">H", size)

    #     a = bytearray(start)
    #     b = bytearray(size)
    #     self.con._write(b"<SPIR" + a + b + b">>")
    #     for i in range(10):
    #         time.sleep(0.1 * (1 + i))
    #         data = self.con._read()
    #         if len(data) > 0:
    #             break
    #     #         data = self.con.get(b'<SPIR' + a + b + b'>>')
    #     return data

    # def _all_history(self):
    #     data = b""
    #     read_chunk = 2**11  # 2048
    #     max_size = 2**20  # 1MB?
    #     for start in range(0, max_size, read_chunk):
    #         kb = start / 1024
    #         print("Loading {0:,.0f} kB".format(kb), end="\r")
    #         #             print('Reading', start, end='\r')
    #         tmp = self._history(start, read_chunk)
    #         if len(tmp) == 0:
    #             print("no data")
    #             break
    #         data += tmp
    #         if tmp.count(b"\xff") >= read_chunk * 0.5:
    #             print("End of history")
    #             break
    #     return data
