#!/usr/bin/env python
# coding: utf-8

import os
import time
import unittest

import k3fs
import k3proc
import k3thread
import k3ut
import k3num

dd = k3ut.dd

# k3fs/test/
this_base = os.path.dirname(__file__)

pyt = 'python'


class TestFS(unittest.TestCase):
    def test_exceptions(self):

        dd('present: ', k3fs.FSUtilError)
        dd('present: ', k3fs.NotMountPoint)

    def test_get_all_mountpoint(self):
        mps = k3fs.get_all_mountpoint()
        dd('mount points:', mps)
        self.assertIn('/', mps)

        mpsall = k3fs.get_all_mountpoint(all=True)
        dd('all mount points:', mps)

        self.assertTrue(len(mpsall) > len(mps))
        self.assertEqual(set([]), set(mps) - set(mpsall))

    def test_mountpoint(self):

        cases = (
            ('/', '/',),
            ('/bin/ls', '/',),
            ('/dev', '/dev',),
            ('/dev/', '/dev',),
            ('/dev/random', '/dev',),
            ('/dev/inexistent', '/dev',),
        )

        for path, expected in cases:
            dd(path, ' --> ', expected)

            rst = k3fs.get_mountpoint(path)
            dd('rst: ', rst)

            self.assertEqual(expected, rst)

            # test assert_mount_point

            k3fs.assert_mountpoint(rst)
            self.assertRaises(k3fs.NotMountPoint,
                              k3fs.assert_mountpoint, path + '/aaa')

    def test_get_disk_partitions(self):

        rst = k3fs.get_disk_partitions()

        self.assertIn('/', rst)

        root = rst['/']
        for k in ('device', 'mountpoint', 'fstype', 'opts'):
            self.assertIn(k, root)

        notall = k3fs.get_disk_partitions(all=False)
        self.assertTrue(len(rst) > len(notall))
        self.assertEqual(set([]), set(notall) - set(rst))

    def test_get_device(self):
        if is_ci():
            return
        rst = k3fs.get_device('/inexistent')

        # GNU "grep -o" split items into several lines
        root_dev = k3proc.shell_script(
            'mount | grep " on / " | grep -o "[^ ]*" | head -n1')[1].strip()

        self.assertEqual(root_dev, rst)

    def test_get_device_fs(self):
        if is_ci():
            return
        # GNU "grep -o" split items into several lines
        rc, out, err = k3proc.shell_script(
            'mount | grep " on / " | grep -o "[^ ]*" | head -n1')
        dd('find device on /', rc, out, err)

        dev = out.strip()
        dd('device: ', dev)
        rst = k3fs.get_device_fs(dev)
        self.assertIn(rst, ('hfs', 'xfs', 'ext2', 'ext3', 'ext4'))

    def test_get_path_fs(self):

        rst = k3fs.get_path_fs('/dev')
        dd('fs of /dev: ', rst)
        self.assertNotEqual('unknown', rst)
        self.assertTrue('dev' in rst)

        rst = k3fs.get_path_fs('/blabla')
        dd('fs of /blabla: ', rst)
        self.assertIn(rst, ('hfs', 'xfs', 'ext2', 'ext3', 'ext4'))

    def test_get_path_usage(self):

        path = '/'
        rst = k3fs.get_path_usage(path)

        # check against os.statvfs.
        st = os.statvfs(path)

        dd(k3num.readable(rst))

        # space is changing..

        self.assertAlmostEqual(st.f_frsize * st.f_bavail, rst['available'], delta=4 * 1024 ** 2)
        self.assertAlmostEqual(st.f_frsize * st.f_blocks, rst['total'], delta=4 * 1024 ** 2)
        self.assertAlmostEqual(st.f_frsize * (st.f_blocks - st.f_bavail), rst['used'], delta=4 * 1024 ** 2)
        self.assertAlmostEqual((st.f_blocks - st.f_bavail) * 100 / st.f_blocks,
                               int(rst['percent'] * 100), delta=4 * 1024 ** 2)

        if st.f_bfree > st.f_bavail:
            self.assertLess(rst['available'], st.f_frsize * st.f_bfree)
        else:
            dd('st.f_bfree == st.f_bavail')

        # check against df

        rc, out, err = k3proc.shell_script('df -m / | tail -n1')
        # Filesystem 1M-blocks   Used Available Capacity  iused    ifree %iused  Mounted on
        # /dev/disk1    475828 328021    147556    69% 84037441 37774557   69%   /
        dd('space of "/" from df')
        total_mb = out.strip().split()[1]

        # "123.8M", keep int only
        rst_total_mb = k3num.readable(rst['total'], unit=k3num.M)
        rst_total_mb = rst_total_mb.split('.')[0].split('M')[0]

        dd('total MB from df:', total_mb, 'result total MB:', rst_total_mb)

        self.assertAlmostEqual(int(total_mb), int(rst_total_mb), delta=4)

    def test_get_path_inode_usage(self):

        inode_st = k3fs.get_path_inode_usage('/')

        self.assertGreaterEqual(inode_st['percent'], 0.0, '')
        self.assertLessEqual(inode_st['percent'], 1.0, '')
        self.assertLessEqual(inode_st['used'], inode_st['total'])

        total = inode_st['used'] + inode_st['available']
        self.assertEqual(inode_st['total'], total)

    def test_makedirs(self):

        fn = '/tmp/pykit-ut-k3fs-foo'
        fn_part = ('/tmp', 'pykit-ut-k3fs-foo')
        dd('fn_part:', fn_part)

        force_remove(fn)

        dd('file is not a dir')
        with open(fn, 'w') as f:
            f.write('a')
        self.assertRaises(OSError, k3fs.makedirs, fn)
        os.unlink(fn)

        dd('no error if dir exist')
        os.mkdir(fn)
        k3fs.makedirs(fn)
        os.rmdir(fn)

        dd('single part path should be created')
        k3fs.makedirs(fn)
        self.assertTrue(os.path.isdir(fn))
        os.rmdir(fn)

        dd('multi part path should be created')
        k3fs.makedirs(*fn_part)
        self.assertTrue(os.path.isdir(fn), 'multi part path should be created')
        os.rmdir(fn)

        dd('default mode')
        k3fs.makedirs(fn)
        self.assertEqual(0o755, get_mode(fn))
        os.rmdir(fn)

        dd('specify mode')
        k3fs.makedirs(fn, mode=0o700)
        self.assertEqual(0o700, get_mode(fn))
        os.rmdir(fn)

        dd('specify uid/gid, to change uid, you need root privilege')
        # dd('changing uid/gid works if it raises error')
        # self.assertRaises(PermissionError, k3fs.makedirs, fn, uid=1, gid=1)
        k3fs.makedirs(fn, uid=1, gid=1)

    def test_ls_dirs(self):
        k3fs.makedirs('test_dir/sub_dir1/foo')
        k3fs.makedirs('test_dir/sub_dir2')
        k3fs.fwrite('test_dir/test_file', 'foo')

        sub_dirs = k3fs.ls_dirs('test_dir')
        self.assertListEqual(['sub_dir1', 'sub_dir2'], sub_dirs)

        # test multi path segment
        sub_dirs = k3fs.ls_dirs('test_dir', 'sub_dir1')
        self.assertListEqual(['foo'], sub_dirs)

        k3fs.remove('test_dir')

    def test_ls_files(self):

        k3fs.makedirs('test_dir/foo_dir')

        k3fs.fwrite('test_dir/foo1', 'foo1')
        k3fs.fwrite('test_dir/foo2', 'foo2')
        k3fs.fwrite('test_dir/foo21', 'foo21')
        k3fs.fwrite('test_dir/foo_dir/foo', 'foo')
        k3fs.fwrite('test_dir/foo_dir/bar', 'bar')

        self.assertEqual(['foo1', 'foo2', 'foo21'], k3fs.ls_files('test_dir'))
        self.assertEqual(['foo2'], k3fs.ls_files('test_dir', pattern='2$'))

        self.assertEqual(['bar', 'foo'], k3fs.ls_files('test_dir/foo_dir'))
        self.assertEqual(['bar'], k3fs.ls_files('test_dir/foo_dir', pattern='^b'))

        # test multi path segments
        self.assertEqual(['bar', 'foo'], k3fs.ls_files('test_dir', 'foo_dir'))

        k3fs.remove('test_dir')

    def test_makedirs_with_config(self):

        fn = '/tmp/pykit-ut-k3fs-foo'
        force_remove(fn)

        rc, out, err = k3proc.shell_script(pyt + ' ' + this_base + '/makedirs_with_config.py ' + fn,
                                           env=dict(PYTHONPATH=this_base + ':' + os.environ.get('PYTHONPATH'),
                                                    PATH=os.environ.get('PATH'))
                                           )

        dd('run makedirs_with_config.py: ', rc, out, err)

        self.assertEqual(0, rc, 'normal exit')
        self.assertEqual('2,3', out, 'uid,gid is defined in test/pykitconfig.py')

    def test_read_write_file(self):

        fn = '/tmp/pykit-ut-rw-file'
        force_remove(fn)

        dd('write/read file')
        k3fs.fwrite(fn, 'bar')
        self.assertEqual('bar', k3fs.fread(fn))

        # write with multi path segment
        k3fs.fwrite('/tmp', 'pykit-ut-rw-file', '123')
        self.assertEqual('123', k3fs.fread(fn))

        # read with multi path segment
        self.assertEqual('123', k3fs.fread('/tmp', 'pykit-ut-rw-file'))

        self.assertEqual(b'123', k3fs.fread(fn, mode='b'))

        dd('write/read 3MB file')
        cont = '123' * (1024 ** 2)

        k3fs.fwrite(fn, cont)
        self.assertEqual(cont, k3fs.fread(fn))

        dd('write file with uid/gid')
        k3fs.fwrite(fn, '1', uid=1, gid=1)
        stat = os.stat(fn)
        self.assertEqual(1, stat.st_uid)
        self.assertEqual(1, stat.st_gid)

        force_remove(fn)

    def test_write_file_with_config(self):

        fn = '/tmp/pykit-ut-k3fs-foo'
        force_remove(fn)

        rc, out, err = k3proc.shell_script(pyt + ' ' + this_base + '/write_with_config.py ' + fn,
                                           env=dict(PYTHONPATH=this_base + ':' + os.environ.get('PYTHONPATH'))
                                           )

        dd('run write_with_config.py: ', rc, out, err)

        self.assertEqual(0, rc, 'normal exit')
        self.assertEqual('2,3', out, 'uid,gid is defined in test/pykitconfig.py')

        force_remove(fn)

    def test_write_file_atomically(self):

        fn = '/tmp/pykit-ut-k3fs-write-atomic'

        dd('atomically write file')

        cont_thread1 = 'cont_thread1'
        cont_thread2 = 'cont_thread2'

        os_fsync = os.fsync

        def _wait_fsync(fildes):
            time.sleep(3)

            os_fsync(fildes)

        os.fsync = _wait_fsync

        assert_ok = {'ok': True}

        def _write_wait(cont_write, cont_read, start_after, atomic):

            time.sleep(start_after)

            k3fs.fwrite(fn, cont_write, atomic=atomic)

            if cont_read != k3fs.fread(fn):
                assert_ok['ok'] = False

        force_remove(fn)
        # atomic=False
        #  time     file    thread1     thread2
        #   0      cont_1   w_cont_1    sleep()
        #  1.5     cont_2   sleep()     w_cont_2
        #   3      cont_2   return      sleep()
        #  4.5     cont_2    None       return

        ths = []
        th = k3thread.daemon(_write_wait,
                             args=(cont_thread1, cont_thread2, 0, False))
        ths.append(th)

        th = k3thread.daemon(_write_wait,
                             args=(cont_thread2, cont_thread2, 1.5, False))
        ths.append(th)

        for th in ths:
            th.join()
        self.assertTrue(assert_ok['ok'])

        force_remove(fn)
        # atomic=True
        #  time     file    thread1     thread2
        #   0       None    w_cont_1    sleep()
        #  1.5      None    sleep()     w_cont_2
        #   3      cont_1   return      sleep()
        #  4.5     cont_2    None       return

        ths = []
        th = k3thread.daemon(_write_wait,
                             args=(cont_thread1, cont_thread1, 0, True))
        ths.append(th)

        th = k3thread.daemon(_write_wait,
                             args=(cont_thread2, cont_thread2, 1.5, True))
        ths.append(th)

        for th in ths:
            th.join()
        self.assertTrue(assert_ok['ok'])

        os.fsync = os_fsync
        force_remove(fn)

    def test_remove_normal_file(self):

        f = 'pykit-ut-k3fs-remove-file-normal'
        fn = '/tmp/' + f
        force_remove(fn)

        k3fs.fwrite(fn, '', atomic=True)
        self.assertTrue(os.path.isfile(fn))

        k3fs.remove(fn)
        self.assertFalse(os.path.exists(fn))

        k3fs.fwrite('/tmp', f, '', atomic=True)
        self.assertTrue(os.path.isfile(fn))

        # remove with multi path segments
        k3fs.remove('/tmp', f)
        self.assertFalse(os.path.exists(fn))

    def test_remove_link_file(self):

        src_fn = '/tmp/pykit-ut-k3fs-remove-file-normal'
        force_remove(src_fn)

        k3fs.fwrite(src_fn, '', atomic=True)
        self.assertTrue(os.path.isfile(src_fn))

        link_fn = '/tmp/pykit-ut-k3fs-remove-file-link'
        force_remove(link_fn)

        os.link(src_fn, link_fn)
        self.assertTrue(os.path.isfile(link_fn))

        k3fs.remove(link_fn)
        self.assertFalse(os.path.exists(link_fn))

        symlink_fn = '/tmp/pykit-ut-k3fs-remove-file-symlink'
        force_remove(symlink_fn)

        os.symlink(src_fn, symlink_fn)
        self.assertTrue(os.path.islink(symlink_fn))

        k3fs.remove(symlink_fn)
        self.assertFalse(os.path.exists(symlink_fn))

        force_remove(src_fn)

    def test_remove_dir(self):

        dirname = '/tmp/pykit-ut-k3fs-remove-dir'

        k3fs.makedirs(dirname)
        self.assertTrue(os.path.isdir(dirname))

        for is_dir, file_path in (
                (False, ('normal_file',)),
                (True, ('sub_dir',)),
                (False, ('sub_dir', 'sub_file1')),
                (False, ('sub_dir', 'sub_file2')),
                (True, ('sub_empty_dir',)),
                (True, ('sub_dir', 'sub_sub_dir')),
                (False, ('sub_dir', 'sub_sub_dir', 'sub_sub_file')),
        ):

            path = os.path.join(dirname, *file_path)

            if is_dir:
                k3fs.makedirs(path)
                self.assertTrue(os.path.isdir(path))
            else:
                k3fs.fwrite(path, '')
                self.assertTrue(os.path.isfile(path))

        k3fs.remove(dirname)
        self.assertFalse(os.path.exists(dirname))

    def test_remove_dir_with_link(self):

        dirname = '/tmp/pykit-ut-k3fs-remove-dir'

        k3fs.makedirs(dirname)
        self.assertTrue(os.path.isdir(dirname))

        normal_file = 'normal_file'
        normal_path = os.path.join(dirname, normal_file)

        k3fs.fwrite(normal_path, '')
        self.assertTrue(os.path.isfile(normal_path))

        hard_link = 'hard_link'
        hard_path = os.path.join(dirname, hard_link)

        os.link(normal_path, hard_path)
        self.assertTrue(os.path.isfile(hard_path))

        symbolic_link = 'symbolic_link'
        symbolic_path = os.path.join(dirname, symbolic_link)

        os.symlink(hard_path, symbolic_path)
        self.assertTrue(os.path.islink(symbolic_path))

        k3fs.remove(dirname)
        self.assertFalse(os.path.exists(dirname))

    def test_remove_error(self):

        dirname = '/tmp/pykit-ut-k3fs-remove-on-error'
        if os.path.isdir(dirname):
            k3fs.remove(dirname)

        # OSError
        self.assertRaises(os.error, k3fs.remove, dirname, onerror='raise')

        # ignore errors
        k3fs.remove(dirname, onerror='ignore')

        def assert_error(exp_func):
            def onerror(func, path, exc_info):
                self.assertEqual(func, exp_func)

            return onerror

        # on error
        k3fs.remove(dirname, onerror=assert_error(os.remove))

    def test_calc_checksums(self):

        M = 1024 ** 2

        fn = '/tmp/pykit-ut-fsutil-calc_checksums'
        force_remove(fn)

        cases = (
            ('',
             {
                 'sha1': True,
                 'md5': True,
                 'crc32': True,
                 'sha256': True,
                 'block_size': M,
                 'io_limit': M,
             },
             {
                 'sha1': 'da39a3ee5e6b4b0d3255bfef95601890afd80709',
                 'md5': 'd41d8cd98f00b204e9800998ecf8427e',
                 'crc32': '00000000',
                 'sha256': 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
             },
             None,
             ),

            ('',
             {
                 'md5': True,
                 'crc32': True,
             },
             {
                 'sha1': None,
                 'md5': 'd41d8cd98f00b204e9800998ecf8427e',
                 'crc32': '00000000',
                 'sha256': None,
             },
             None,
             ),

            ('',
             {
             },
             {
                 'sha1': None,
                 'md5': None,
                 'crc32': None,
                 'sha256': None,
             },
             None,
             ),

            ('It  바로 とても 氣!',
             {
                 'sha1': True,
                 'md5': True,
                 'crc32': True,
                 'sha256': True,
                 'block_size': M,
                 'io_limit': M,
             },
             {
                 'sha1': 'e22fa5446cb33d0c32221d89ee270dff23e32847',
                 'md5': '9d245fca88360be492c715253d68ba6f',
                 'crc32': '7c3becdb',
                 'sha256': '7327753b12db5c0dd090ad802c1c8ff44ea4cb447f3091d43cab371bd7583d9a',
             },
             None,
             ),

            ('It  바로 とても 氣!',
             {
                 'sha1': False,
                 'md5': True,
                 'crc32': True,
                 'sha256': False,
                 'block_size': M,
                 'io_limit': M,
             },
             {
                 'sha1': None,
                 'md5': '9d245fca88360be492c715253d68ba6f',
                 'crc32': '7c3becdb',
                 'sha256': None,
             },
             None,
             ),

            ('It  바로 とても 氣!',
             {
                 'sha1': True,
                 'md5': False,
                 'crc32': False,
                 'sha256': True,
             },
             {
                 'sha1': 'e22fa5446cb33d0c32221d89ee270dff23e32847',
                 'md5': None,
                 'crc32': None,
                 'sha256': '7327753b12db5c0dd090ad802c1c8ff44ea4cb447f3091d43cab371bd7583d9a',
             },
             None,
             ),

            ('!' * M * 10,
             {
                 'sha1': False,
                 'md5': False,
                 'crc32': False,
                 'sha256': False,
                 'block_size': M,
                 'io_limit': M,
             },
             {
                 'sha1': None,
                 'md5': None,
                 'crc32': None,
                 'sha256': None,
             },
             (0, 0.5),
             ),

            ('!' * M * 10,
             {
                 'sha1': True,
                 'md5': True,
                 'crc32': True,
                 'sha256': True,
                 'block_size': M * 10,
                 'io_limit': M * 10,
             },
             {
                 'sha1': 'c5430d624c498024d0f3371670227a201e910054',
                 'md5': '8f499b17375fc678c7256f3c0054db79',
                 'crc32': 'f0af209f',
                 'sha256': 'bd5263cc56b27fda9f86f41f6d2ec012eb60d757281003c363b88677c7dcc5e7',

             },
             (1, 1.5),
             ),

            ('!' * M * 10,
             {
                 'sha1': True,
                 'block_size': M,
                 'io_limit': M * 5,
             },
             None,
             (2, 2.5),
             ),

            ('!' * M * 10,
             {
                 'sha1': True,
                 'block_size': M,
                 'io_limit': -1,
             },
             None,
             (0, 0.5),
             ),
        )

        for cont, args, exp_checksums, min_time in cases:

            force_remove(fn)
            k3fs.fwrite(fn, cont)

            t0 = time.time()
            checksums = k3fs.calc_checksums(fn, **args)
            spend_time = time.time() - t0

            if exp_checksums is not None:
                for k in checksums:
                    self.assertEqual(exp_checksums[k], checksums[k],
                                     'except: {exp}, actuality: {act}'.format(
                                         exp=exp_checksums[k],
                                         act=checksums[k],
                                     ))

            if min_time is not None:
                self.assertTrue(min_time[0] < spend_time < min_time[1])

        force_remove(fn)


def force_remove(fn):
    try:
        os.rmdir(fn)
    except BaseException:
        pass

    try:
        os.unlink(fn)
    except BaseException:
        pass


def get_mode(fn):
    mode = os.stat(fn).st_mode
    dd('mode read:', oct(mode))
    return mode & 0o777


def is_ci():
    # github ci
    return os.environ.get('CI', "") is not None
